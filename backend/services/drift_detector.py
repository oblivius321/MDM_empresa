"""
Drift Detector — Orquestrador de enforcement de policies MDM.

Conecta a Policy Engine (pure functions) ao banco de dados e à CommandQueue.

Responsabilidades:
  1. Calcular o Master Profile (merged) de um device
  2. Comparar actual vs desired via hash O(1)
  3. Gerar subcomandos granulares via detect_drift()
  4. Despachar subcomandos pela CommandQueue existente
  5. Anti-loop: travar enforcement quando falha se repete
  6. Rate limit: máximo de N enforcements por hora por device

Nunca envia nada diretamente para o WebSocket.
Sempre usa dispatch_command() da Fase 2.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from backend.services.policy_engine import (
    merge_policies,
    compute_effective_hash,
    compute_hash,
    detect_drift,
    compute_drift_summary,
)

logger = logging.getLogger("drift_detector")

# ─── Rate Limit Config ────────────────────────────────────────────────────────
MAX_ENFORCEMENTS_PER_HOUR = 10  # Máximo de ciclos de enforcement por device/hora
_enforcement_timestamps: Dict[str, List[float]] = {}  # device_id → [timestamps]

# ─── Enforcement Lock por Device ──────────────────────────────────────────────
_enforcement_locks: Dict[str, asyncio.Lock] = {}


def _get_enforcement_lock(device_id: str) -> asyncio.Lock:
    if device_id not in _enforcement_locks:
        _enforcement_locks[device_id] = asyncio.Lock()
    return _enforcement_locks[device_id]


def _check_rate_limit(device_id: str) -> bool:
    """
    Retorna True se o device pode ser enforced agora.
    Remove timestamps > 1 hora e verifica o limite.
    """
    now = time.monotonic()
    cutoff = now - 3600  # 1 hora

    if device_id not in _enforcement_timestamps:
        _enforcement_timestamps[device_id] = []

    # Limpa timestamps antigos
    _enforcement_timestamps[device_id] = [
        ts for ts in _enforcement_timestamps[device_id] if ts > cutoff
    ]

    if len(_enforcement_timestamps[device_id]) >= MAX_ENFORCEMENTS_PER_HOUR:
        logger.warning(
            f"⛔ [RateLimit] device={device_id} atingiu {MAX_ENFORCEMENTS_PER_HOUR} "
            f"enforcements/hora. Bloqueando."
        )
        return False

    _enforcement_timestamps[device_id].append(now)
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES PÚBLICAS
# ═══════════════════════════════════════════════════════════════════════════════

async def get_device_desired_state(device_id: str) -> Tuple[dict, str]:
    """
    Calcula o Master Profile (merged) para um device.

    Retorna: (merged_config, effective_hash)
    """
    from backend.core.database import async_session_maker
    from backend.models.policy import DevicePolicy, DevicePolicyAssignment, Policy, ProvisioningProfilePolicy
    from sqlalchemy.future import select

    async with async_session_maker() as db:
        profile_result = await db.execute(
            select(DevicePolicy.profile_id).where(DevicePolicy.device_id == device_id)
        )
        profile_id = profile_result.scalar_one_or_none()

        policies: List[Policy] = []

        if profile_id is not None:
            result = await db.execute(
                select(Policy)
                .join(ProvisioningProfilePolicy, ProvisioningProfilePolicy.policy_id == Policy.id)
                .where(
                    ProvisioningProfilePolicy.profile_id == profile_id,
                    Policy.is_active == True,
                )
                .order_by(ProvisioningProfilePolicy.priority.asc())
            )
            policies.extend(result.scalars().all())

        direct_result = await db.execute(
            select(Policy)
            .join(DevicePolicyAssignment, DevicePolicyAssignment.policy_id == Policy.id)
            .where(
                DevicePolicyAssignment.device_id == device_id,
                Policy.is_active == True,
            )
            .order_by(Policy.priority.asc())
        )
        policies.extend(direct_result.scalars().all())

        # Dedupe por id preservando a política com maior precedência de scope/priority.
        scope_order = {"global": 0, "group": 1, "device": 2}
        policies = sorted(
            {policy.id: policy for policy in policies}.values(),
            key=lambda policy: (scope_order.get(policy.scope, 0), policy.priority),
        )

        if not policies:
            return {}, ""

        # Prepara lista para merge
        policy_dicts = [
            {
                "config": p.config or {},
                "priority": p.priority,
                "scope": p.scope,
            }
            for p in policies
        ]

        # Calcula o merged config
        merged = merge_policies(policy_dicts)

        # Effective hash inclui a maior versão entre as policies
        max_version = max(p.version for p in policies)
        effective_hash = compute_effective_hash(max_version, merged)

        return merged, effective_hash


async def evaluate_compliance(
    device_id: str,
    reported_state: Optional[dict] = None,
) -> dict:
    """
    Avalia compliance de um device.

    Fluxo:
      1. Calcula desired state (merge de policies)
      2. Compara com actual state (do DB ou do parâmetro)
      3. Se drift → gera subcomandos e enfileira na CommandQueue
      4. Atualiza PolicyState

    Retorna dict com resultado de compliance.
    """
    from backend.core.database import async_session_maker
    from backend.models.policy import PolicyState
    from sqlalchemy.future import select

    lock = _get_enforcement_lock(device_id)
    async with lock:
        return await _do_evaluate(device_id, reported_state)


async def _do_evaluate(
    device_id: str,
    reported_state: Optional[dict],
) -> dict:
    """Lógica interna de avaliação (dentro do lock do device)."""
    from backend.core.database import async_session_maker
    from backend.models.policy import PolicyState
    from sqlalchemy.future import select

    # ── 1. Desired State ──────────────────────────────────────────────────────
    desired, effective_hash = await get_device_desired_state(device_id)

    if not desired:
        logger.info(f"📋 [Compliance] device={device_id}: nenhuma policy atribuída")
        return {"device_id": device_id, "status": "no_policies", "compliant": True}

    # ── 2. Actual State ───────────────────────────────────────────────────────
    async with async_session_maker() as db:
        row = await db.execute(
            select(PolicyState).where(PolicyState.device_id == device_id)
        )
        state = row.scalar_one_or_none()

        if not state:
            # Primeiro ciclo: cria o PolicyState
            state = PolicyState(
                device_id=device_id,
                last_compliance_status="unknown",
            )
            db.add(state)

        # Se veio um novo reported_state, atualiza no DB
        if reported_state:
            state.last_reported_state = reported_state
            state.state_hash = compute_hash(reported_state)

        # Atualiza o effective_policy_hash (cache)
        state.effective_policy_hash = effective_hash

        actual = state.last_reported_state or {}
        device_hash = state.state_hash or ""

        # ── 3. Comparação O(1) por hash ───────────────────────────────────────
        if effective_hash == device_hash and device_hash:
            state.last_compliance_status = "compliant"
            state.drift_score = 0
            await db.commit()
            logger.info(f"✅ [Compliance] device={device_id}: COMPLIANT (hash match)")
            return {
                "device_id": device_id,
                "status": "compliant",
                "compliant": True,
                "effective_hash": effective_hash,
            }

        # ── 4. Deep Diff (hashes não bateram) ─────────────────────────────────
        subcommands = detect_drift(desired, actual)

        if not subcommands:
            # Hashes diferentes mas sem drift real (pode ser campo novo sem valor)
            state.last_compliance_status = "compliant"
            state.state_hash = effective_hash  # Sincroniza
            await db.commit()
            logger.info(f"✅ [Compliance] device={device_id}: COMPLIANT (no drift)")
            return {
                "device_id": device_id,
                "status": "compliant",
                "compliant": True,
            }

        # ── 5. Anti-Loop Check ────────────────────────────────────────────────
        if state.last_compliance_status == "failed_loop":
            logger.warning(
                f"🔒 [AntiLoop] device={device_id}: em failed_loop. "
                f"Enforcement bloqueado até mudança de policy version."
            )
            return {
                "device_id": device_id,
                "status": "failed_loop",
                "compliant": False,
                "blocked": True,
            }

        # ── 6. Rate Limit Check ───────────────────────────────────────────────
        if not _check_rate_limit(device_id):
            return {
                "device_id": device_id,
                "status": "rate_limited",
                "compliant": False,
                "blocked": True,
            }

        # ── 7. Despachar subcomandos via CommandQueue ─────────────────────────
        from backend.core import utcnow
        state.last_compliance_status = "enforcing"
        state.last_enforced_at = utcnow()
        state.enforcement_count = (state.enforcement_count or 0) + 1
        state.drift_score = (state.drift_score or 0) + len(subcommands)
        await db.commit()

    # Dispatch fora do db context para não travar a session
    dispatched = await _dispatch_subcommands(device_id, subcommands)

    summary = compute_drift_summary(desired, actual)
    logger.info(
        f"🔧 [Enforcement] device={device_id}: {len(dispatched)} subcomandos "
        f"despachados | drift_categories={summary['drifted_categories']}"
    )

    return {
        "device_id": device_id,
        "status": "enforcing",
        "compliant": False,
        "subcommands_dispatched": len(dispatched),
        "drift_summary": summary,
    }


async def _dispatch_subcommands(
    device_id: str,
    subcommands: List[dict],
) -> List[dict]:
    """
    Despacha subcomandos via CommandQueue existente.

    Usa dispatch_command() da Fase 2 para herdar:
    - Idempotência (dedupe_key)
    - Backpressure (limite por device)
    - Retry + DLQ
    - Métricas e auditoria
    """
    from backend.api.command_dispatcher import dispatch_command
    from backend.services.mdm_service import MDMService
    from backend.core.database import async_session_maker
    from backend.repositories.device_repo import DeviceRepository
    from backend.api.websockets import manager

    dispatched = []

    async with async_session_maker() as db:
        repo = DeviceRepository(db)
        service = MDMService(repo)

        for sc in subcommands:
            try:
                result = await dispatch_command(
                    service=service,
                    manager=manager,
                    device_id=device_id,
                    action=sc["action"],
                    payload=sc.get("payload", {}),
                    issued_by="system:policy_enforcement",
                )
                dispatched.append(result)
                logger.info(
                    f"📤 [Dispatch] device={device_id} action={sc['action']} "
                    f"→ cmd_id={result.get('command_id')}"
                )
            except OverflowError:
                logger.warning(
                    f"⛔ [Backpressure] device={device_id}: fila cheia, "
                    f"abortando enforcement de {sc['action']}"
                )
                break
            except Exception as e:
                logger.error(
                    f"❌ [Dispatch] device={device_id} action={sc['action']} erro: {e}"
                )

    return dispatched


async def handle_subcommand_result(
    device_id: str,
    action: str,
    success: bool,
) -> None:
    """
    Chamado quando um subcomando de policy completa ou falha.

    Atualiza o PolicyState:
    - Se todos completaram → compliant
    - Se alguns falharam → enforcing_partial + failed_subcommands
    - Se o mesmo subcomando falha repetidamente → failed_loop
    """
    from backend.core.database import async_session_maker
    from backend.models.policy import PolicyState
    from sqlalchemy.future import select

    async with async_session_maker() as db:
        row = await db.execute(
            select(PolicyState).where(PolicyState.device_id == device_id)
        )
        state = row.scalar_one_or_none()

        if not state:
            return

        failed_subs = list(state.failed_subcommands or [])

        if not success:
            if action not in failed_subs:
                failed_subs.append(action)
            state.failed_subcommands = failed_subs

            # Anti-loop: se o mesmo subcomando falhar 3+ vezes, trava
            fail_count = failed_subs.count(action) if isinstance(failed_subs, list) else 0
            # Conta repetições marcadas pelo drift_score crescente
            if state.enforcement_count and state.enforcement_count >= 3 and action in failed_subs:
                state.last_compliance_status = "failed_loop"
                logger.error(
                    f"🔒 [AntiLoop] device={device_id}: action={action} falhou "
                    f"repetidamente. Status → failed_loop."
                )
            else:
                state.last_compliance_status = "enforcing_partial"
        else:
            # Removeu o subcomando da lista de falhos
            if action in failed_subs:
                failed_subs.remove(action)
            state.failed_subcommands = failed_subs

            # Se não há mais falhos pendentes → compliant
            if not failed_subs:
                state.last_compliance_status = "compliant"
                state.drift_score = 0
                logger.info(f"✅ [Compliance] device={device_id}: COMPLIANT após enforcement")

        await db.commit()
