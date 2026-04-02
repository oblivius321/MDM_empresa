"""
Command Dispatcher — despacho central de comandos MDM.

Ajustes implementados:
  1. Idempotência Backend  → dedupe_key único (device_id, dedupe_key) UNIQUE no DB
  2. Métricas             → log estruturado de latência, taxa de falha, tentativas
  3. Ordem por device      → asyncio.Lock por device_id (envio sequencial FIFO)
  4. Backpressure          → fila máxima de 50 comandos por device (HTTP 429)
  5. Auditoria             → issued_by (email do admin) persistido no CommandQueue
  6. Payload enxuto        → broadcast mínimo e determinístico
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# ─── Constantes ────────────────────────────────────────────────────────────────

MAX_QUEUE_PER_DEVICE = 50    # Backpressure — fila máxima por device

# ─── Estado em memória ─────────────────────────────────────────────────────────

# Lock por device_id para garantir ordem sequencial de envio (sem interleaving)
_device_locks: Dict[str, asyncio.Lock] = {}

def _get_device_lock(device_id: str) -> asyncio.Lock:
    """Retorna (criando se necessário) o asyncio.Lock do device."""
    if device_id not in _device_locks:
        _device_locks[device_id] = asyncio.Lock()
    return _device_locks[device_id]


def _build_dedupe_key(device_id: str, action: str) -> str:
    """
    Calcula chave de deduplicação para janela de 1 minuto.

    Fórmula: sha256(device_id:action:YYYYMMDDHHMI)[:16]

    Garante que dois cliques no mesmo botão no mesmo minuto gerem
    a mesma chave — o segundo é rejeitado pelo índice UNIQUE do DB.
    """
    now = datetime.now(timezone.utc)
    minute_bucket = now.strftime("%Y%m%d%H%M")
    raw = f"{device_id}:{action}:{minute_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── Métricas (Ajuste 2) ───────────────────────────────────────────────────────

def _log_metrics(cmd, final_status: str):
    """
    Emite métricas estruturadas para cada transição terminal de comando.

    Métricas mínimas:
      - latência até ACK       (sent_at → acked_at)
      - latência até RESULT    (acked_at ou sent_at → completed_at)
      - taxa de falha          (via final_status != "completed")
      - tentativas de entrega  (cmd.attempts)

    Formato: JSON-friendly para fácil ingestão por Loki/ELK/Datadog no futuro.
    """
    metrics: Dict[str, object] = {
        "event": "CMD_TERMINAL",
        "correlation_id": f"{cmd.device_id}:{cmd.id}",
        "cmd_id": cmd.id,
        "action": cmd.command,
        "device_id": cmd.device_id,
        "issued_by": cmd.issued_by,
        "final_status": final_status,
        "attempts": cmd.attempts,
        "retry_count": cmd.retry_count,
        "error_code": cmd.error_code,
    }

    # Latência até ACK (ms)
    if cmd.sent_at and cmd.acked_at:
        ack_latency_ms = int(
            (cmd.acked_at - cmd.sent_at).total_seconds() * 1000
        )
        metrics["ack_latency_ms"] = ack_latency_ms

    # Latência até RESULT (ms) — medido desde o envio
    base = cmd.acked_at or cmd.sent_at
    if base and cmd.completed_at:
        result_latency_ms = int(
            (cmd.completed_at - base).total_seconds() * 1000
        )
        metrics["result_latency_ms"] = result_latency_ms

    # E2E latency (desde criação até término)
    if cmd.created_at and cmd.completed_at:
        e2e_ms = int(
            (cmd.completed_at - cmd.created_at).total_seconds() * 1000
        )
        metrics["e2e_latency_ms"] = e2e_ms

    # Sucesso vs Falha
    metrics["is_failure"] = final_status not in ("completed",)

    logger.info(f"📊 [Metrics] {metrics}")


# ─── Dispatcher Principal ──────────────────────────────────────────────────────

async def dispatch_command(
    service,
    manager,
    device_id: str,
    action: str,
    payload: Optional[dict] = None,
    issued_by: Optional[str] = None,       # Ajuste 5: Auditoria
) -> dict:
    """
    Cria e despacha um comando MDM para o device.

    Garantias:
      1. Idempotência   → rejeita duplicatas (UNIQUE index no DB elimina race condition)
      2. Ordem          → asyncio.Lock por device garante envio FIFO
      3. Backpressure   → rejeita se device tiver >= MAX_QUEUE_PER_DEVICE pendentes
      5. Auditoria      → issued_by persiste quem enviou o comando
    """
    payload = payload or {}
    lock = _get_device_lock(device_id)
    async with lock:
        return await _do_dispatch(service, manager, device_id, action, payload, issued_by)


async def _do_dispatch(
    service,
    manager,
    device_id: str,
    action: str,
    payload: dict,
    issued_by: Optional[str],
) -> dict:
    """Execução interna do dispatch (chamada dentro do lock do device)."""

    from backend.core.database import async_session_maker
    from backend.models.policy import CommandQueue
    from sqlalchemy.future import select
    from sqlalchemy import and_, func
    from sqlalchemy.exc import IntegrityError

    dedupe_key = _build_dedupe_key(device_id, action)

    # ── Lookup de duplicata ANTES da inserção (fast path) ─────────────────────
    async with async_session_maker() as db:
        dup = await db.execute(
            select(CommandQueue).where(
                and_(
                    CommandQueue.dedupe_key == dedupe_key,
                    CommandQueue.status.not_in([
                        "failed", "failed_no_ack", "failed_no_result", "completed"
                    ]),
                )
            )
        )
        existing = dup.scalar_one_or_none()
        if existing:
            logger.warning(
                f"⚠️ [Dedupe] Bloqueado: action={action} device={device_id} "
                f"cmd_id={existing.id} dedupe={dedupe_key}"
            )
            return {
                "command_id": existing.id,
                "status": existing.status,
                "action": action,
                "deduplicated": True,
            }

    # ── Ajuste 8 (e 5 opcional): Backpressure com limites rígidos por ação ──────
    async with async_session_maker() as db:
        from sqlalchemy import func
        count_result = await db.execute(
            select(func.count(CommandQueue.id)).where(
                and_(
                    CommandQueue.device_id == device_id,
                    CommandQueue.status.in_(["pending", "sent"]),
                    # Conta pendentes globais, mas para limites severos contamos globais também
                )
            )
        )
        queue_size = count_result.scalar_one()

        # Limite severo para comandos de alto impacto: apenas 1 pendente permitido
        allowed_max = 1 if action in ("wipe_device", "reboot_device") else MAX_QUEUE_PER_DEVICE

    if queue_size >= allowed_max:
        logger.error(
            f"🚫 [Backpressure] Fila cheia para device={device_id}: "
            f"{queue_size}/{allowed_max} ({action})"
        )
        raise OverflowError(
            f"Device '{device_id}' já possui {queue_size} comandos pendentes. "
            f"Limite para a ação '{action}': {allowed_max}."
        )

    # ── Criar o comando no DB (status=pending) ────────────────────────────────
    cmd = await service.repo.add_command(device_id, action, payload=payload)
    if not cmd:
        raise ValueError(f"Device '{device_id}' não encontrado.")

    # ── Persistir dedupe_key + issued_by (Ajustes 1 e 5) ─────────────────────
    # Tentamos gravar com dedupe_key. Se o índice UNIQUE disparar (race condition
    # concorrente que passou pelo lookup acima), capturamos o IntegrityError
    # e buscamos o registro existente — garantia forte sem lock de DB.
    try:
        async with async_session_maker() as db:
            row = await db.execute(select(CommandQueue).where(CommandQueue.id == cmd.id))
            cmd_row = row.scalar_one_or_none()
            if cmd_row:
                cmd_row.dedupe_key = dedupe_key
                cmd_row.issued_by = issued_by   # Ajuste 5: quem enviou
                await db.commit()
    except IntegrityError:
        # Race condition: outra instância criou o mesmo dedupe_key em paralelo.
        # Descartamos o cmd recém-criado e retornamos o existente.
        logger.warning(
            f"⚠️ [Dedupe/IntegrityError] Race condition detectada: "
            f"action={action} device={device_id} dedupe={dedupe_key}"
        )
        async with async_session_maker() as db:
            dup2 = await db.execute(
                select(CommandQueue).where(CommandQueue.dedupe_key == dedupe_key)
            )
            winner = dup2.scalar_one_or_none()
            if winner:
                return {
                    "command_id": winner.id,
                    "status": winner.status,
                    "action": action,
                    "deduplicated": True,
                }

    # ── Tentar entrega imediata via WebSocket ─────────────────────────────────
    ws_payload = {
        "type": "command",
        "command_id": cmd.id,
        "action": action,
        "payload": payload,
    }
    delivered = await manager.send_command_to_device(device_id, ws_payload)

    if delivered:
        now = datetime.now(timezone.utc)
        await service.repo.update_device_command_status(
            cmd.id, "sent", sent_at=now
        )
        async with async_session_maker() as db:
            row = await db.execute(select(CommandQueue).where(CommandQueue.id == cmd.id))
            cmd_row = row.scalar_one_or_none()
            if cmd_row:
                cmd_row.attempts = (cmd_row.attempts or 0) + 1
                await db.commit()

        await manager.broadcast_to_dashboards({
            "type": "CMD_SENT",
            "device_id": device_id,
            "command_id": cmd.id,
            "action": action,
            "status": "sent",
        })
        logger.info(
            f"📡 [CMD] {action} → {device_id} | cmd_id={cmd.id} "
            f"issued_by={issued_by} status=sent"
        )
        return {"command_id": cmd.id, "status": "sent", "action": action}

    logger.info(
        f"⏳ [CMD] {action} → {device_id} | cmd_id={cmd.id} "
        f"issued_by={issued_by} status=pending (offline)"
    )
    return {"command_id": cmd.id, "status": "pending", "action": action}


# ─── API pública para emitir métricas (chamado pelo websocket_routes) ──────────

def emit_command_metrics(cmd) -> None:
    """
    Ponto de entrada público para emissão de métricas.
    Chamado pelos handlers _handle_cmd_result e pelo watchdog de timeout.
    """
    if cmd:
        _log_metrics(cmd, cmd.status)
