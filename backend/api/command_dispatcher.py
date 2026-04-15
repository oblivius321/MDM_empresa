"""
Command Dispatcher — despacho central de comandos MDM em conformidade com a arquitetura SaaS de 3 camadas.

Ajustes para a nova Command Engine:
  1. Idempotência      -utiliza dedupe_key e status PENDING/DISPATCHED/ACKED/EXECUTED/FAILED.
  2. Ordem por device   -asyncio.Lock por device_id para garantir FIFO no WebSocket.
  3. Backpressure       limites de fila por dispositivo (MAX_QUEUE_PER_DEVICE).
  4. Auditoria           Eventos registrados via DeviceRepository.log_event.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import timedelta
from typing import Optional, Dict
from sqlalchemy.future import select
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError

from backend.core import async_session_maker, CommandStatus, utcnow

logger = logging.getLogger(__name__)

# ─── Constantes ──

MAX_QUEUE_PER_DEVICE = 50    # Backpressure — fila máxima por device

# ─── Estado em memória ──

# Lock por device_id para garantir ordem sequencial de envio (sem interleaving)
_device_locks: Dict[str, asyncio.Lock] = {}

def _get_device_lock(device_id: str) -> asyncio.Lock:
    """Retorna (criando se necessário) o asyncio.Lock do device."""
    if device_id not in _device_locks:
        _device_locks[device_id] = asyncio.Lock()
    return _device_locks[device_id]


def _build_dedupe_key(device_id: str, action: str, payload: dict) -> str:
    """
    Calcula chave de deduplicação canônica para janela de 1 minuto.
    """
    now = utcnow()
    minute_bucket = now.strftime("%Y%m%d%H%M")
    # Canonical JSON for consistent hashing
    payload_json = json.dumps(payload or {}, sort_keys=True, separators=(',', ':'))
    raw = f"{device_id}:{action}:{payload_json}:{minute_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ─── Dispatcher Principal ──────────────────────────────────────────────────────

async def dispatch_command(
    service,
    manager,
    device_id: str,
    action: str,
    payload: Optional[dict] = None,
    issued_by: Optional[str] = None,
) -> dict:
    """
    Cria e despacha um comando MDM para o device.
    Garante que as ações sejam sequenciais para o dispositivo via Lock.
    """
    payload = payload or {}
    lock = _get_device_lock(device_id)
    async with lock:
        try:
            return await _do_dispatch(service, manager, device_id, action, payload, issued_by)
        except Exception as e:
            logger.error(f"❌ Erro fatal no dispatch de {action} para {device_id}: {e}")
            raise


async def _do_dispatch(
    service,
    manager,
    device_id: str,
    action: str,
    payload: dict,
    issued_by: Optional[str],
) -> dict:
    """Execução interna do dispatch (chamada dentro do lock do device)."""

    dedupe_key = _build_dedupe_key(device_id, action, payload)

    # ── 1. Lookup de duplicata ativa (fast path) ──────────────────────────────
    async with async_session_maker() as db:
        from backend.models.policy import CommandQueue
        dup = await db.execute(
            select(CommandQueue).where(
                and_(
                    CommandQueue.dedupe_key == dedupe_key,
                    CommandQueue.status.in_([CommandStatus.PENDING, CommandStatus.DISPATCHED]),
                )
            )
        )
        existing = dup.scalars().first()
        if existing:
            logger.warning(f"⚠️ [Dedupe] Comando ignorado por duplicidade ativa: {action} em {device_id}")
            return {
                "command_id": str(existing.id),
                "status": existing.status,
                "action": action,
                "deduplicated": True,
            }

    # ── 2. Backpressure — Limites de fila ─────────────────────────────────────
    async with async_session_maker() as db:
        from backend.models.policy import CommandQueue
        count_result = await db.execute(
            select(func.count(CommandQueue.id)).where(
                and_(
                    CommandQueue.device_id == device_id,
                    CommandQueue.status.in_([CommandStatus.PENDING, CommandStatus.DISPATCHED]),
                )
            )
        )
        queue_size = count_result.scalar_one()

        # Comandos críticos ocupam a fila sozinhos por segurança
        allowed_max = 1 if action in ("wipe_device", "reboot_device") else MAX_QUEUE_PER_DEVICE

    if queue_size >= allowed_max:
        logger.error(f"🚫 [Backpressure] Fila cheia para {device_id}: {queue_size}/{allowed_max}")
        raise OverflowError(f"O dispositivo já possui muitos comandos pendentes. Limite: {allowed_max}.")

    # ── 3. Criar comando via SERVICE ──────────────────────────────────────────
    try:
        cmd = await service.enqueue_command(
            device_id=device_id,
            command_type=action,
            actor_id=issued_by or "system",
            payload=payload,
            dedupe_key=dedupe_key,
        )
    except Exception as e:
        if "dedupe" in str(e).lower() or "unique" in str(e).lower():
            logger.warning(f"⚠️ [Integrity] Colisão de dedupe detectada em {device_id}:{action}")
            return {"status": "duplicate", "action": action}
        raise

    # ── 4. Tentar entrega imediata via WebSocket ──
    if cmd.status in (CommandStatus.ACKED, CommandStatus.FAILED):
        broadcast_type = "CMD_FAILED" if cmd.status == CommandStatus.FAILED else "CMD_COMPLETED"
        try:
            await manager.broadcast_to_dashboards({
                "type": broadcast_type,
                "device_id": device_id,
                "command_id": str(cmd.id),
                "action": action,
                "status": cmd.status,
                "transport": (cmd.payload or {}).get("transport"),
                "error": cmd.error_message,
            })
        except Exception as e:
            logger.error(f"Erro ao notificar dashboard sobre comando AMAPI: {e}")
        return {
            "command_id": str(cmd.id),
            "status": cmd.status,
            "action": action,
            "transport": (cmd.payload or {}).get("transport"),
        }

    ws_payload = {
        "type": "command",
        "command_id": str(cmd.id),
        "action": action,
        "payload": payload,
    }
    
    if manager.is_device_online(device_id):
        try:
            async with async_session_maker() as db:
                from backend.repositories.device_repo import DeviceRepository
                from backend.models.policy import CommandQueue as CQ
                repo = DeviceRepository(db)
                c_obj = await db.get(CQ, cmd.id)
                if c_obj:
                    await repo.transition_status(c_obj, CommandStatus.DISPATCHED)
                    await db.commit()
            
            delivered = await manager.send_command_to_device(device_id, ws_payload)
            if delivered:
                await manager.broadcast_to_dashboards({
                    "type": "CMD_SENT",
                    "device_id": device_id,
                    "command_id": str(cmd.id),
                    "action": action,
                    "status": CommandStatus.DISPATCHED,
                })
                logger.info(f"📡 [CMD Dispatch] {action} enviado para {device_id} via WebSocket.")
                return {"command_id": str(cmd.id), "status": CommandStatus.DISPATCHED, "action": action}
        except Exception as e:
            logger.error(f"Erro ao transicionar para DISPATCHED no envio imediato: {e}")

    # Se o device estiver offline ou falhou entrega, permanece como PENDING
    logger.info(f"⏳ [CMD Queued] {action} aguardando checkin de {device_id} (offline/penitente).")
    return {"command_id": str(cmd.id), "status": CommandStatus.PENDING, "action": action}
