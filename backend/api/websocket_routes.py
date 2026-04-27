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
from backend.core import async_session_maker, CommandStatus, utcnow

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
        
        unverified_header = jwt.get_unverified_header(token)
        if unverified_header.get("alg") != ALGORITHM:
            raise JWTError("Invalid token algorithm")
            
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
    Entrega todos os comandos (PENDING + DISPATCHED) para o device logo após conectar.
    Sincronizado com o pipeline Enterprise.
    """
    from backend.core.database import async_session_maker
    from backend.repositories.device_repo import DeviceRepository
    from backend.models.policy import CommandQueue
    from sqlalchemy import and_

    logger.info(f"🔄 [Flush] Sincronizando comandos pendentes para device={device_id}")

    sent_count = 0
    try:
        async with async_session_maker() as db:
            repo = DeviceRepository(db)

            # Busca comandos que ainda não expiraram ou falharam definitivamente
            result = await db.execute(
                select(CommandQueue)
                .where(
                    and_(
                        CommandQueue.device_id == device_id,
                        CommandQueue.status.in_([CommandStatus.PENDING, CommandStatus.DISPATCHED]),
                    )
                )
                .order_by(CommandQueue.created_at.asc())
            )
            commands = result.scalars().all()

            for cmd in commands:
                # Verificação de retries excedidos (DLQ)
                if (cmd.attempts or 0) >= cmd.max_retries:
                    await repo.transition_status(cmd, CommandStatus.FAILED, metadata={"error": "max_retries_reached"})
                    await db.commit()
                    continue

                ws_payload = {
                    "type": "command",
                    "command_id": str(cmd.id),
                    "action": cmd.command,
                    "payload": cmd.payload or {},
                }
                
                try:
                    await websocket.send_json(ws_payload)
                    
                    # Se estava PENDING, movemos para DISPATCHED. 
                    # Se já estava DISPATCHED, apenas atualizamos sent_at (retry/resume).
                    if cmd.status == CommandStatus.PENDING:
                        await repo.transition_status(cmd, CommandStatus.DISPATCHED)
                    else:
                        cmd.sent_at = utcnow()
                    
                    # Incrementamos retry_count a cada envio físico
                    cmd.retry_count = (cmd.retry_count or 0) + 1
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
    Processa confirmação de transporte (ACK) do device. 
    O device apenas diz: 'Recebi o comando'.
    Mantemos em DISPATCHED ou apenas logamos, pois o pipeline oficial 
    espera o resultado final (EXECUTED) para avançar.
    """
    command_id = data.get("command_id")
    if not command_id: return
    try:
        command_id = int(command_id)
    except (TypeError, ValueError):
        logger.warning(f"[cmd_ack] command_id invalido: {command_id}")
        return

    try:
        async with async_session_maker() as db:
            from backend.models.policy import CommandQueue
            row = await db.execute(
                select(CommandQueue).where(
                    CommandQueue.id == command_id,
                    CommandQueue.device_id == device_id
                )
            )
            cmd = row.scalar_one_or_none()
            if cmd:
                # Opcional: registrar que o transporte foi confirmado
                logger.debug(f"📲 [Transport ACK] Device {device_id} confirmou recebimento de {cmd.id}")
    except Exception as e:
        logger.error(f"[cmd_ack] Erro: {e}")


async def _handle_cmd_result(device_id: str, data: dict):
    """
    Processa resultado de execução do Android.
    Pipeline: ... -> DISPATCHED -> EXECUTED -> ACKED
    """
    command_id = data.get("command_id")
    exec_status = data.get("status", "")
    error_msg = data.get("error")

    if not command_id or exec_status not in ("success", "failed"):
        return
    try:
        command_id = int(command_id)
    except (TypeError, ValueError):
        logger.warning(f"[cmd_result] command_id invalido: {command_id}")
        return

    try:
        async with async_session_maker() as db:
            from backend.repositories.device_repo import DeviceRepository
            from backend.models.policy import CommandQueue
            repo = DeviceRepository(db)
            
            row = await db.execute(
                select(CommandQueue).where(
                    CommandQueue.id == command_id,
                    CommandQueue.device_id == device_id
                )
            )
            cmd = row.scalar_one_or_none()
            
            if not cmd or cmd.status in CommandStatus.TERMINAL_STATES:
                return

            if exec_status == "success":
                # Pipeline Atômico: EXECUTED (Android terminou) -> ACKED (Backend confirmou)
                await repo.transition_status(cmd, CommandStatus.EXECUTED)
                await repo.transition_status(cmd, CommandStatus.ACKED)
                final_status = CommandStatus.ACKED
                broadcast_type = "CMD_COMPLETED"
            else:
                cmd.error_message = error_msg or "Android reported failure"
                await repo.transition_status(cmd, CommandStatus.FAILED)
                final_status = CommandStatus.FAILED
                broadcast_type = "CMD_FAILED"

            await db.commit()

            # Notifica Dashboard
            await manager.broadcast_to_dashboards({
                "type": broadcast_type,
                "device_id": device_id,
                "command_id": str(cmd.id),
                "action": cmd.command,
                "status": final_status,
                "error": error_msg
            })
            
            logger.info(f"🏁 [cmd_result] {cmd.command} para {device_id} finalizado como {final_status}")

    except Exception as e:
        logger.error(f"[cmd_result] Erro ao processar resultado: {e}")


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
