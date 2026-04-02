"""
websocket_routes.py — WebSocket handlers para Elion MDM.

Protocolo de presença:
  Device → Backend : {"type": "ping"}           (a cada 30s)
  Backend → Device : {"type": "server_ping"}    (a cada 30s)

Protocolo de comandos:
  Backend → Device : {"type": "command", "command_id": int, "action": str, "payload": {}}
  Device → Backend : {"type": "cmd_ack",    "command_id": int}
  Device → Backend : {"type": "cmd_result", "command_id": int, "status": "success"|"failed", "error": str|null}

Fontes de Verdade:
  - Presença:  heartbeat timeout (Watchdog)
  - Comandos:  DB (CommandQueue) — single source of truth
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
import asyncio
from datetime import datetime, timezone

from backend.api.websockets import (
    manager,
    HEARTBEAT_TIMEOUT_SECONDS,
    HEARTBEAT_MIN_INTERVAL,
    WS_CLOSE_AUTH_FAILED,
    WS_CLOSE_HB_TIMEOUT,
)
from backend.core.security import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
from sqlalchemy.future import select
from backend.core.database import async_session_maker
from backend.models.device import Device
from backend.api.device_auth import verify_device_token
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Intervalo de server_ping (heartbeat bidirecional)
SERVER_PING_INTERVAL = 30   # segundos

# Timeout para comandos enviados (sent/acked) sem resposta do device
COMMAND_TIMEOUT_SECONDS = 120  # 2 minutos


# ─── Dashboard ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """
    [ACCEPT-FIRST] Dashboard Admin.
    Autenticação via JWT dentro do túnel.
    """
    await websocket.accept()
    logger.info("Handshake Dashboard: [101] concedido.")

    token = websocket.cookies.get("access_token")
    try:
        if not token:
            raise JWTError("Token ausente nos cookies.")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise JWTError("Payload JWT inválido.")

        await manager.connect_dashboard(websocket)
        await websocket.send_json({
            "status": "authenticated",
            "message": "Radar Elion MDM Conectado.",
            "user": email,
        })

    except (JWTError, Exception) as e:
        logger.warning(f"Rejeição Dashboard: {e}")
        await websocket.send_json({"status": "unauthorized", "message": str(e)})
        await websocket.close(code=WS_CLOSE_AUTH_FAILED)
        return

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("ping")
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)
        logger.info("Dashboard desconectado.")
    except Exception as e:
        logger.error(f"Erro no loop Dashboard: {e}")
        manager.disconnect_dashboard(websocket)


# ─── Device ────────────────────────────────────────────────────────────────────

@router.websocket("/ws/device/{device_id}")
async def websocket_device(websocket: WebSocket, device_id: str):
    """
    [ACCEPT-FIRST] Android Agent.

    Após autenticação:
      1. Flush de comandos pendentes (pending + sent, ordenado por created_at)
      2. Loop de presença + receiver de mensagens
    """
    await websocket.accept()
    logger.info(f"Handshake Device {device_id}: [101] concedido.")

    # ── AUTENTICAÇÃO ────────────────────────────────────────────────────────────
    token = websocket.headers.get("x-device-token")
    try:
        if not token:
            raise Exception("X-Device-Token ausente.")

        async with async_session_maker() as db:
            result = await db.execute(select(Device).where(Device.device_id == device_id))
            device = result.scalar_one_or_none()

            if not device or not device.is_active or not device.api_key_hash:
                raise Exception(f"Device '{device_id}' inativo ou não registrado.")

            if not verify_device_token(token, device.api_key_hash):
                raise Exception("Token inválido.")

        # Conexão autenticada → registra na malha + persiste online no DB
        await manager.connect_device(websocket, device_id)
        await manager._write_status_to_db(device_id, "online")
        manager.presence.mark_db_synced(device_id)

        await websocket.send_json({
            "type": "CONNECTED",
            "device_id": device_id,
            "heartbeat_interval": SERVER_PING_INTERVAL,
        })

        # ── FLUSH DE COMANDOS PENDENTES (Reconnect Recovery) ──────────────────
        # Busca comandos pending + sent, ordenados por created_at ASC.
        # Isso garante que o device receba comandos que ficaram parados durante
        # a desconexão anterior, na ordem correta de criação.
        await _flush_pending_commands(websocket, device_id)

        # ── COMPLIANCE CHECK NO CONNECT (Fase 3) ──────────────────────────────
        # Após o flush de comandos pendentes, verifica compliance do device.
        # Se houver drift, novos subcomandos serão enfileirados automaticamente.
        try:
            from backend.services.drift_detector import evaluate_compliance
            asyncio.create_task(evaluate_compliance(device_id))
        except Exception as e:
            logger.error(f"[Compliance] Erro ao avaliar no connect: {e}")

    except Exception as e:
        logger.warning(f"Rejeição Device {device_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "message": "unauthorized"})
        except Exception:
            pass
        await websocket.close(code=WS_CLOSE_AUTH_FAILED)
        return

    # ── LOOP CONCORRENTE: Receiver + Server Ping ────────────────────────────────
    receiver_task = asyncio.create_task(
        _device_receiver(websocket, device_id)
    )
    server_ping_task = asyncio.create_task(
        _server_ping_loop(websocket, device_id)
    )

    try:
        done, pending = await asyncio.wait(
            {receiver_task, server_ping_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Cancelamento seguro — aguarda finalização total para evitar memory leak
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"Erro no loop device={device_id}: {e}")
        for t in (receiver_task, server_ping_task):
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

    finally:
        await manager.disconnect_device(device_id, reason="loop_ended")


# ─── Flush de Comandos Pendentes ───────────────────────────────────────────────

async def _flush_pending_commands(websocket: WebSocket, device_id: str):
    """
    Entrega todos os comandos (pending + sent) para o device logo após conectar.

    Ordem: created_at ASC (garante execução na sequência correta).
    Atualiza status para 'sent' após entrega bem-sucedida.

    Idempotência:
      - Device deve ignorar command_id já executado (verificando localmente).
      - Backend nunca marca como 'sent' se já estiver em estado terminal
        (completed/failed).
    """
    from backend.core.database import async_session_maker
    from backend.repositories.device_repo import DeviceRepository
    from backend.models.policy import CommandQueue
    from sqlalchemy import and_

    logger.info(f"🔄 [Flush] Buscando comandos pendentes para device={device_id}")

    sent_count = 0
    try:
        async with async_session_maker() as db:
            repo = DeviceRepository(db)

            result = await db.execute(
                select(CommandQueue)
                .where(
                    and_(
                        CommandQueue.device_id == device_id,
                        CommandQueue.status.in_(["pending", "sent"]),
                    )
                )
                .order_by(CommandQueue.created_at.asc())
            )
            commands = result.scalars().all()

            for cmd in commands:
                # Ajuste 6: Dead Letter Queue (DLQ) leve
                if cmd.retry_count >= cmd.max_retries:
                    cmd.status = "failed"
                    cmd.error_code = "max_retries"
                    cmd.error_message = f"Esgotou {cmd.max_retries} tentativas de envio"
                    cmd.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    
                    await manager.broadcast_to_dashboards({
                        "type": "CMD_FAILED",
                        "device_id": cmd.device_id,
                        "command_id": cmd.id,
                        "action": cmd.command,
                        "status": "failed",
                        "error": cmd.error_message,
                    })
                    
                    try:
                        from backend.api.command_dispatcher import emit_command_metrics
                        emit_command_metrics(cmd)
                    except Exception:
                        pass
                    
                    logger.warning(
                        f"🚫 [DLQ] cmd_id={cmd.id} action={cmd.command} "
                        f"→ failed_max_retries"
                    )
                    continue


                # Ajuste 4: Backoff simples — delay cresce com retry_count
                # retry 0 → 0s, retry 1 → 5s, retry 2 → 15s
                backoff_delays = [0, 5, 15]
                delay = backoff_delays[min(cmd.retry_count, len(backoff_delays) - 1)]
                if delay > 0:
                    await asyncio.sleep(delay)

                ws_payload = {
                    "type": "command",
                    "command_id": cmd.id,
                    "action": cmd.command,
                    "payload": cmd.payload or {},
                }
                try:
                    await websocket.send_json(ws_payload)
                    if cmd.status == "pending":
                        await repo.update_device_command_status(
                            cmd.id, "sent", sent_at=datetime.now(timezone.utc)
                        )
                    # Incrementa contador de retry e attempts
                    cmd.retry_count = (cmd.retry_count or 0) + 1
                    cmd.attempts = (cmd.attempts or 0) + 1
                    await db.commit()

                    sent_count += 1
                    logger.info(
                        f"📤 [Flush] cmd_id={cmd.id} action={cmd.command} "
                        f"→ {device_id} (retry={cmd.retry_count})"
                    )
                except Exception as e:
                    logger.error(
                        f"[Flush] Falha ao enviar cmd_id={cmd.id} para {device_id}: {e}"
                    )
                    break  # Socket problemático — interrompe o flush

    except Exception as e:
        logger.error(f"[Flush] Erro ao buscar comandos para {device_id}: {e}")

    if sent_count:
        logger.info(f"✅ [Flush] {sent_count} comando(s) enviado(s) para {device_id}")
    else:
        logger.debug(f"[Flush] Sem comandos pendentes para {device_id}")


# ─── Receiver: Mensagens do Device ─────────────────────────────────────────────

async def _device_receiver(websocket: WebSocket, device_id: str):
    """
    Loop receptor de mensagens JSON do device.

    Handlers:
      - ping         → heartbeat (com flood protection)
      - cmd_ack      → atualiza CommandQueue: sent → acked
      - cmd_result   → atualiza CommandQueue: acked → completed | failed
      - (qualquer outro) → hearbeat implícito + broadcast

    Timeout = HEARTBEAT_TIMEOUT_SECONDS.
    Ao expirar, fecha o socket com código 4003 (heartbeat_timeout).
    """
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=float(HEARTBEAT_TIMEOUT_SECONDS),
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"⏱️ Timeout: device={device_id} — silêncio > {HEARTBEAT_TIMEOUT_SECONDS}s. "
                    f"Fechando com código {WS_CLOSE_HB_TIMEOUT}."
                )
                await websocket.close(code=WS_CLOSE_HB_TIMEOUT)
                return

            msg_type = data.get("type", "")

            # ── HEARTBEAT ────────────────────────────────────────────────────
            if msg_type == "ping":
                if not manager.presence.is_heartbeat_allowed(device_id):
                    logger.debug(
                        f"[Flood] {device_id}: ping ignorado (< {HEARTBEAT_MIN_INTERVAL}s)"
                    )
                    continue

                manager.record_heartbeat(device_id)
                await manager.persist_online_lazy(device_id)
                await websocket.send_json({"type": "pong"})

            # ── COMMAND ACK (Device recebeu o comando) ───────────────────────
            elif msg_type == "cmd_ack":
                await _handle_cmd_ack(device_id, data)

            # ── COMMAND RESULT (Device executou o comando) ───────────────────
            elif msg_type == "cmd_result":
                await _handle_cmd_result(device_id, data)

                # Fase 3: Se o resultado é de um subcomando de policy, atualiza compliance
                action = data.get("action", "")
                if action.startswith("apply_") or action.startswith("uninstall_"):
                    try:
                        from backend.services.drift_detector import handle_subcommand_result
                        exec_status = data.get("status", "")
                        await handle_subcommand_result(
                            device_id, action, success=(exec_status == "success")
                        )
                    except Exception as e:
                        logger.error(f"[Compliance] Erro ao processar result de policy: {e}")

            # ── STATE REPORT (Fase 3: Device reporta estado atual) ────────────
            elif msg_type == "state_report":
                manager.record_heartbeat(device_id)
                state_data = data.get("state", data)
                logger.info(f"📱 [StateReport/WS] device={device_id}: keys={list(state_data.keys())}")

                try:
                    from backend.services.drift_detector import evaluate_compliance
                    result = await evaluate_compliance(device_id, reported_state=state_data)
                    # Envia resultado de compliance de volta ao device
                    await websocket.send_json({
                        "type": "compliance_status",
                        "status": result.get("status", "unknown"),
                        "compliant": result.get("compliant", False),
                    })
                    # Notifica dashboard
                    await manager.broadcast_to_dashboards({
                        "type": "COMPLIANCE_UPDATE",
                        "device_id": device_id,
                        "status": result.get("status", "unknown"),
                        "compliant": result.get("compliant", False),
                    })
                except Exception as e:
                    logger.error(f"[StateReport] Erro ao avaliar compliance: {e}")

            # ── HEARTBEAT IMPLÍCITO (qualquer outra mensagem) ────────────────
            else:
                manager.record_heartbeat(device_id)
                await manager.broadcast_to_dashboards({
                    "type": "DEVICE_EVENT",
                    "device_id": device_id,
                    "status": "online",
                    "payload": data,
                })

    except WebSocketDisconnect:
        logger.info(f"Device {device_id} desconectou (WebSocketDisconnect).")


# ─── Handlers de Comandos (chamados pelo receiver) ─────────────────────────────

async def _handle_cmd_ack(device_id: str, data: dict):
    """
    Processa ACK de comando: sent → acked.

    Idempotente: se o comando já estiver em estado terminal (completed/failed),
    ignora silenciosamente (o device pode reenviar ACK após reconnect).
    """
    command_id = data.get("command_id")
    if not command_id:
        logger.warning(f"[cmd_ack] cmd_ack sem command_id de device={device_id}")
        return

    try:
        async with async_session_maker() as db:
            from backend.repositories.device_repo import DeviceRepository
            from backend.models.policy import CommandQueue
            repo = DeviceRepository(db)

            # Ajuste 6: Validação de propriedade — garante que o comando pertence ao device
            row = await db.execute(
                select(CommandQueue).where(
                    CommandQueue.id == command_id,
                    CommandQueue.device_id == device_id,   # owner check
                )
            )
            cmd = row.scalar_one_or_none()
            if not cmd:
                logger.warning(
                    f"🚫 [cmd_ack] OWNERSHIP VIOLATION: cmd_id={command_id} "
                    f"não pertence a device={device_id}"
                )
                return

            # Idempotente: ignora se já está em estado terminal
            if cmd.status in ("completed", "failed", "failed_no_ack", "failed_no_result"):
                logger.debug(f"[cmd_ack] cmd_id={command_id} já terminal ({cmd.status}). Ignorando.")
                return

            cmd.status = "acked"
            cmd.acked_at = datetime.now(timezone.utc)
            await db.commit()

        await manager.broadcast_to_dashboards({
            "type": "CMD_ACKED",
            "device_id": device_id,
            "command_id": command_id,
            "action": cmd.command,
            "status": "acked",
        })
        logger.info(f"✅ [cmd_ack] cmd_id={command_id} acked por device={device_id}")

    except Exception as e:
        logger.error(f"[cmd_ack] Erro ao processar ack cmd_id={command_id}: {e}")


async def _handle_cmd_result(device_id: str, data: dict):
    """
    Processa resultado de execução: acked → completed | failed.

    Idempotente: se cmd_id já estiver em estado terminal, ignora (evita duplicados
    em caso de retry do device pós-reconnect).

    Payload esperado:
        { "type": "cmd_result", "command_id": int, "status": "success"|"failed", "error": str|null }
    """
    command_id = data.get("command_id")
    exec_status = data.get("status", "")
    error_msg = data.get("error")

    if not command_id or exec_status not in ("success", "failed"):
        logger.warning(
            f"[cmd_result] Payload inválido de device={device_id}: {data}"
        )
        return

    try:
        async with async_session_maker() as db:
            from backend.repositories.device_repo import DeviceRepository
            repo = DeviceRepository(db)

            # ─ Idempotência: Não regredir estado terminal ─────────────────────
            from backend.models.policy import CommandQueue
            row = await db.execute(
                select(CommandQueue).where(
                    CommandQueue.id == command_id,
                    CommandQueue.device_id == device_id,
                )
            )
            existing_cmd = row.scalar_one_or_none()

            # Ajuste 6: Validação de propriedade explícita
            if not existing_cmd:
                logger.warning(
                    f"🚫 [cmd_result] OWNERSHIP VIOLATION: cmd_id={command_id} "
                    f"não pertence a device={device_id} ou não existe"
                )
                return

            # Idempotência: não regredir estado terminal (inclui sub-estados de falha)
            TERMINAL_STATES = ("completed", "failed", "failed_no_ack", "failed_no_result")
            if existing_cmd.status in TERMINAL_STATES:
                logger.debug(
                    f"[cmd_result] cmd_id={command_id} já em estado terminal "
                    f"({existing_cmd.status}). Ignorando."
                )
                return

            # ─ Atualizar status ───────────────────────────────────────────────
            if exec_status == "success":
                ok = await repo.complete_command_secure(device_id, command_id)
                final_status = "completed"
                broadcast_type = "CMD_COMPLETED"
            else:
                ok = await repo.fail_command_secure(
                    device_id, command_id, error_msg or "Device reported failure"
                )
                final_status = "failed"
                broadcast_type = "CMD_FAILED"

        if not ok:
            logger.warning(
                f"[cmd_result] cmd_id={command_id} não encontrado ou não pertence a {device_id}"
            )
            return

        # Broadcast para o dashboard com estado final (payload mínimo)
        action = existing_cmd.command if existing_cmd else "unknown"
        await manager.broadcast_to_dashboards({
            "type": broadcast_type,
            "device_id": device_id,
            "command_id": command_id,
            "action": action,
            "status": final_status,
            "error": error_msg,
        })
        logger.info(
            f"🏁 [cmd_result] cmd_id={command_id} {final_status} "
            f"por device={device_id} | action={action}"
        )

        # Ajuste 2: Emite métricas de latência e telemetria
        # Recarrega o cmd do DB para incluir timestamps atualizados
        try:
            async with async_session_maker() as db2:
                from backend.models.policy import CommandQueue as CQ
                row = await db2.execute(
                    select(CQ).where(CQ.id == command_id)
                )
                updated_cmd = row.scalar_one_or_none()
                if updated_cmd:
                    from backend.api.command_dispatcher import emit_command_metrics
                    emit_command_metrics(updated_cmd)
        except Exception:
            pass  # Métricas nunca devem quebrar o fluxo principal

    except Exception as e:
        logger.error(f"[cmd_result] Erro ao processar result cmd_id={command_id}: {e}")


# ─── Server Ping (Heartbeat Bidirecional) ──────────────────────────────────────

async def _server_ping_loop(websocket: WebSocket, device_id: str):
    """
    Heartbeat bidirecional iniciado pelo BACKEND.

    Envia {"type": "server_ping"} a cada SERVER_PING_INTERVAL segundos.
    Detecta NAT timeout, conexão travada, app em background.

    CancelledError é repropagado para asyncio marcar a task corretamente.
    """
    try:
        while True:
            await asyncio.sleep(SERVER_PING_INTERVAL)
            await websocket.send_json({"type": "server_ping"})
    except asyncio.CancelledError:
        logger.debug(f"Server ping cancelado para device={device_id}")
        raise
    except Exception as e:
        logger.warning(f"Server ping encerrado para device={device_id}: {e}")
