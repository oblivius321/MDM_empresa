"""
AMAPI Operation Poller — Background worker for polling Google long-running operations.

Polls commands in DISPATCHED state that have an operation_id,
and advances them to EXECUTED or FAILED based on the Google API response.

Lifecycle:
    PENDING → DISPATCHED (by mdm_service._route_command_to_amapi)
    DISPATCHED → EXECUTED  (by this poller, when Google says done+response)
    DISPATCHED → FAILED    (by this poller, when Google says done+error or stale timeout)
"""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy.future import select
from sqlalchemy import and_

from backend.core import async_session_maker, CommandStatus, utcnow
from backend.models.policy import CommandQueue
from backend.repositories.device_repo import DeviceRepository

logger = logging.getLogger("mdm.amapi_poller")

# ─── Configuration ─────────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS = 15      # How often the poller runs
BATCH_LIMIT = 50                # Max commands to poll per cycle
STALE_TIMEOUT_HOURS = 24        # Auto-fail commands older than this


async def amapi_operation_poller() -> None:
    """Background async loop that polls AMAPI operations for completion.

    Runs indefinitely. Each cycle:
    1. Fetches DISPATCHED commands with operation_id IS NOT NULL
    2. Polls each operation via Google API
    3. Advances status to EXECUTED or FAILED based on the response
    """
    logger.info("AMAPI_OPERATION_POLLER_STARTED")

    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        try:
            await _poll_cycle()
        except Exception as exc:
            # Never crash the poller — log and continue
            logger.error(
                "AMAPI_OPERATION_POLL_CYCLE_ERROR",
                extra={"error": str(exc)},
                exc_info=True,
            )
            await asyncio.sleep(5)


async def _poll_cycle() -> None:
    """Single poll cycle — fetch and process all pending AMAPI operations."""
    async with async_session_maker() as db:
        now = utcnow()
        stale_cutoff = now - timedelta(hours=STALE_TIMEOUT_HOURS)

        # Fetch DISPATCHED commands with an operation_id
        result = await db.execute(
            select(CommandQueue)
            .where(
                and_(
                    CommandQueue.status == CommandStatus.DISPATCHED,
                    CommandQueue.operation_id.isnot(None),
                )
            )
            .order_by(CommandQueue.created_at.asc())
            .limit(BATCH_LIMIT)
        )
        commands = result.scalars().all()

        if not commands:
            return

        logger.info(
            "AMAPI_OPERATION_POLL_STARTED",
            extra={"command_count": len(commands)},
        )

        repo = DeviceRepository(db)

        for cmd in commands:
            try:
                await _poll_single_command(db, repo, cmd, now, stale_cutoff)
            except Exception as exc:
                # Isolate failures — one bad command doesn't block others
                logger.error(
                    "AMAPI_OPERATION_POLL_ERROR",
                    extra={
                        "command_id": cmd.id,
                        "device_id": cmd.device_id,
                        "operation_id": cmd.operation_id,
                        "error": str(exc),
                    },
                )


async def _poll_single_command(db, repo, cmd, now, stale_cutoff) -> None:
    """Poll a single AMAPI operation and update command status accordingly."""
    from backend.services.android_management_service import AndroidManagementService

    # ── Stale timeout check ──────────────────────────────────────────────────
    if cmd.created_at and cmd.created_at < stale_cutoff:
        logger.warning(
            "AMAPI_OPERATION_STALE_TIMEOUT",
            extra={
                "command_id": cmd.id,
                "device_id": cmd.device_id,
                "operation_id": cmd.operation_id,
                "created_at": str(cmd.created_at),
            },
        )
        cmd.error_code = "AMAPI_STALE_TIMEOUT"
        cmd.error_message = f"Operation not completed within {STALE_TIMEOUT_HOURS}h — auto-failed."
        await repo.transition_status(
            cmd, CommandStatus.FAILED,
            metadata={"error": cmd.error_message, "reason": "stale_timeout"},
        )
        await db.commit()
        return

    # ── Soft timeout check (Alert after 3 minutes) ────────────────────────────
    if cmd.sent_at and (now - cmd.sent_at > timedelta(minutes=3)):
        if not (cmd.payload or {}).get("stalled_alert_sent"):
            logger.warning(
                "AMAPI_OPERATION_STALLED_POLLING",
                extra={
                    "command_id": cmd.id,
                    "device_id": cmd.device_id,
                    "operation_id": cmd.operation_id,
                    "delay_seconds": (now - cmd.sent_at).total_seconds(),
                },
            )
            cmd.payload = {**(cmd.payload or {}), "stalled_alert_sent": True}
            await db.commit()

    # ── Guard: Verify command is still in DISPATCHED state ────────────────────
    if cmd.status != CommandStatus.DISPATCHED:
        return

    logger.debug(
        "AMAPI_OPERATION_POLLING",
        extra={
            "command_id": cmd.id,
            "operation_id": cmd.operation_id,
        },
    )

    # ── Poll Google API ──────────────────────────────────────────────────────
    try:
        service = AndroidManagementService()
        operation = await service.get_operation(cmd.operation_id)
    except Exception as exc:
        # Transient API error — log but do NOT fail the command.
        # The next cycle will retry.
        logger.warning(
            "AMAPI_OPERATION_POLL_API_ERROR",
            extra={
                "command_id": cmd.id,
                "operation_id": cmd.operation_id,
                "error": str(exc),
            },
        )
        return

    # ── Process operation result ─────────────────────────────────────────────
    is_done = operation.get("done", False)

    if not is_done:
        # Operation still running — nothing to do
        return

    # Operation is done — determine success or failure
    error = operation.get("error")
    response = operation.get("response")

    if error:
        # ── CASE 3: Google returned an error ─────────────────────────────────
        error_message = error.get("message", str(error))
        error_code = f"AMAPI_{error.get('code', 'UNKNOWN')}"

        cmd.error_code = error_code
        cmd.error_message = error_message
        cmd.payload = {
            **(cmd.payload or {}),
            "amapi_operation_error": error,
        }

        await repo.transition_status(
            cmd, CommandStatus.FAILED,
            metadata={"error": error_message, "amapi_error": error},
        )
        await db.commit()

        logger.warning(
            "AMAPI_OPERATION_FAILED",
            extra={
                "command_id": cmd.id,
                "device_id": cmd.device_id,
                "operation_id": cmd.operation_id,
                "error_code": error_code,
                "error_message": error_message,
            },
        )
    else:
        # ── CASE 2: Google returned success ──────────────────────────────────
        cmd.payload = {
            **(cmd.payload or {}),
            "amapi_operation_result": response,
        }

        await repo.transition_status(cmd, CommandStatus.EXECUTED)
        await db.commit()

        logger.info(
            "AMAPI_OPERATION_COMPLETED",
            extra={
                "command_id": cmd.id,
                "device_id": cmd.device_id,
                "operation_id": cmd.operation_id,
            },
        )
