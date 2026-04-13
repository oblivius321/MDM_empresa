"""
Rotas de Policy Enterprise (Fase 3) — CRUD + Atribuição + Compliance.

Todas as rotas de admin exigem JWT.
Enforcement é automático via drift_detector.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timezone

from backend.api.auth import get_current_user
from backend.models.user import User
from backend.schemas.policy import (
    PolicyConfigCreate,
    PolicyConfigUpdate,
    PolicyConfigResponse,
    DevicePolicyAssign,
    DevicePolicyResponse,
    ComplianceStatusResponse,
    DeviceStateReport,
)

import logging

logger = logging.getLogger("policy_routes")
router = APIRouter(prefix="/api", tags=["Policies Enterprise"])


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/policies/v2", response_model=PolicyConfigResponse)
async def create_policy(
    data: PolicyConfigCreate,
    current_user: User = Depends(get_current_user),
):
    """
    Cria uma nova policy enterprise com config JSON flexível.
    """
    from backend.core.database import async_session_maker
    from backend.models.policy import Policy

    async with async_session_maker() as db:
        from backend.services.policy_engine import validate_policy_structure
        # Hardening: Validação estrita antes de persistir
        try:
            validate_policy_structure(data.config)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        policy = Policy(
            name=data.name,
            config=data.config,
            priority=data.priority,
            scope=data.scope,
            version=1,
            is_active=True,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)

        # Audit Log Enterprise
        from backend.repositories.device_repo import DeviceRepository
        repo = DeviceRepository(db)
        await repo.log_event(
            event_type="POLICY_CREATED",
            actor_type="admin",
            actor_id=current_user.email,
            severity="INFO",
            payload={"id": str(policy.id), "name": policy.name}
        )

        return policy



@router.get("/policies/v2", response_model=List[PolicyConfigResponse])
async def list_policies(
    scope: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
):
    """Lista policies enterprise com filtros opcionais."""
    from backend.core.database import async_session_maker
    from backend.models.policy import Policy
    from sqlalchemy.future import select

    async with async_session_maker() as db:
        query = select(Policy)
        if scope:
            query = query.where(Policy.scope == scope)
        if is_active is not None:
            query = query.where(Policy.is_active == is_active)
        query = query.order_by(Policy.priority.desc())

        result = await db.execute(query)
        return result.scalars().all()


@router.get("/policies/v2/{policy_id}", response_model=PolicyConfigResponse)
async def get_policy(
    policy_id: int,
    current_user: User = Depends(get_current_user),
):
    """Retorna uma policy específica."""
    from backend.core.database import async_session_maker
    from backend.models.policy import Policy
    from sqlalchemy.future import select

    async with async_session_maker() as db:
        result = await db.execute(
            select(Policy).where(Policy.id == policy_id)
        )
        policy = result.scalar_one_or_none()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        return policy


@router.put("/policies/v2/{policy_id}", response_model=PolicyConfigResponse)
async def update_policy(
    policy_id: int,
    data: PolicyConfigUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Atualiza uma policy. Incrementa version automaticamente.
    Isso invalida caches e força re-enforcement nos devices vinculados.
    """
    from backend.core.database import async_session_maker
    from backend.models.policy import Policy
    from sqlalchemy.future import select

        from backend.services.policy_engine import validate_policy_structure
        from backend.repositories.device_repo import DeviceRepository
        repo = DeviceRepository(db)

        # Atualiza campos fornecidos
        if data.name is not None:
            policy.name = data.name
        if data.config is not None:
            # Senior Hardening: Valida schema e limites (64KB / 100 apps)
            try:
                validate_policy_structure(data.config)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            policy.config = data.config
        if data.priority is not None:
            policy.priority = data.priority
        if data.scope is not None:
            policy.scope = data.scope
        if data.is_active is not None:
            policy.is_active = data.is_active

        # Atomic Version Bump (Anti-Race Condition)
        # P2.0 Hardening: SET version = version + 1 RETURNING version
        new_version = await repo.increment_policy_version(policy_id)
        policy.version = new_version
        policy.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(policy)

        await repo.log_event(
            event_type="POLICY_UPDATED",
            actor_type="admin",
            actor_id=current_user.email,
            severity="INFO",
            payload={"id": str(policy.id), "version": policy.version}
        )


        # Trigger re-enforcement para todos os devices vinculados
        await _trigger_re_enforcement(policy.id)

        return policy


@router.delete("/policies/v2/{policy_id}")
async def delete_policy(
    policy_id: int,
    current_user: User = Depends(get_current_user),
):
    """Desativa uma policy (soft delete via is_active=False)."""
    from backend.core.database import async_session_maker
    from backend.models.policy import Policy
    from sqlalchemy.future import select

    async with async_session_maker() as db:
        result = await db.execute(
            select(Policy).where(Policy.id == policy_id)
        )
        policy = result.scalar_one_or_none()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")

        policy.is_active = False
        policy.version += 1
        await db.commit()

        logger.info(f"🗑️ [Policy] Desativada: id={policy.id} by={current_user.email}")
        return {"detail": "Policy deactivated", "id": policy_id}


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE ↔ POLICY ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/devices/{device_id}/policies/v2",
    response_model=DevicePolicyResponse,
)
async def assign_policy_to_device(
    device_id: str,
    data: DevicePolicyAssign,
    current_user: User = Depends(get_current_user),
):
    """
    Atribui uma policy a um device. Trigger imediato de compliance check.
    """
    from backend.core.database import async_session_maker
    from backend.models.policy import DevicePolicy, Policy
    from sqlalchemy.future import select
    from sqlalchemy import and_

    async with async_session_maker() as db:
        # Verifica se a policy existe
        policy = await db.execute(
            select(Policy).where(Policy.id == data.policy_id)
        )
        if not policy.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Policy not found")

        # Verifica duplicata
        existing = await db.execute(
            select(DevicePolicy).where(
                and_(
                    DevicePolicy.device_id == device_id,
                    DevicePolicy.policy_id == data.policy_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Policy already assigned")

        dp = DevicePolicy(
            device_id=device_id,
            policy_id=data.policy_id,
            issued_by=current_user.email,
        )
        db.add(dp)
        await db.commit()
        await db.refresh(dp)

    logger.info(
        f"🔗 [Assign] policy={data.policy_id} → device={device_id} "
        f"by={current_user.email}"
    )

    # Trigger compliance check imediato
    from backend.services.drift_detector import evaluate_compliance
    await evaluate_compliance(device_id)

    return dp


@router.get(
    "/devices/{device_id}/policies/v2",
    response_model=List[PolicyConfigResponse],
)
async def list_device_policies(
    device_id: str,
    current_user: User = Depends(get_current_user),
):
    """Lista todas as policies atribuídas a um device."""
    from backend.core.database import async_session_maker
    from backend.models.policy import DevicePolicy, Policy
    from sqlalchemy.future import select

    async with async_session_maker() as db:
        result = await db.execute(
            select(Policy)
            .join(DevicePolicy, DevicePolicy.policy_id == Policy.id)
            .where(DevicePolicy.device_id == device_id)
            .order_by(Policy.priority.desc())
        )
        return result.scalars().all()


@router.delete("/devices/{device_id}/policies/v2/{policy_id}")
async def unassign_policy_from_device(
    device_id: str,
    policy_id: int,
    current_user: User = Depends(get_current_user),
):
    """Remove atribuição de policy de um device."""
    from backend.core.database import async_session_maker
    from backend.models.policy import DevicePolicy
    from sqlalchemy.future import select
    from sqlalchemy import and_

    async with async_session_maker() as db:
        result = await db.execute(
            select(DevicePolicy).where(
                and_(
                    DevicePolicy.device_id == device_id,
                    DevicePolicy.policy_id == policy_id,
                )
            )
        )
        dp = result.scalar_one_or_none()
        if not dp:
            raise HTTPException(status_code=404, detail="Assignment not found")

        await db.delete(dp)
        await db.commit()

    logger.info(
        f"🔓 [Unassign] policy={policy_id} ← device={device_id} "
        f"by={current_user.email}"
    )

    # Re-evaluate após remoção
    from backend.services.drift_detector import evaluate_compliance
    await evaluate_compliance(device_id)

    return {"detail": "Policy unassigned", "device_id": device_id, "policy_id": policy_id}


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/devices/{device_id}/compliance",
    response_model=ComplianceStatusResponse,
)
async def get_device_compliance(
    device_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retorna o status de compliance atual de um device."""
    from backend.services.drift_detector import evaluate_compliance
    result = await evaluate_compliance(device_id)
    return result


@router.get("/profiles/{profile_id}/preview", tags=["Policies Enterprise"])
async def preview_profile_merged_policy(
    profile_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Retorna o Master Profile (Merged JSON) resultante das 5 camadas.
    Útil para o Config Preview no frontend.
    """
    from backend.core.database import async_session_maker
    from backend.repositories.device_repo import DeviceRepository
    from backend.services.mdm_service import MDMService
    from backend.services.policy_engine import merge_policies, compute_hash
    import uuid as uuid_pkg

        # Security Hardening: Admin access only
        if not current_user.is_admin:
             raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")

        repo = DeviceRepository(db)
        
        # 1. Fetch Layers
        profile = await repo.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
            
        global_policies = await repo.get_global_policies()
        profile_policies = await repo.get_profile_policies(profile_id)
        
        all_ordered_layers = [
            {
                "id": p.id,
                "name": p.name,
                "config": p.config, 
                "priority": p.priority, 
                "scope": p.scope, 
                "version": p.version
            }
            for p in (global_policies + profile_policies)
        ]
        
        profile_static = {
            "kiosk_enabled": profile.kiosk_enabled,
            "allowed_apps": profile.allowed_apps,
            "blocked_features": profile.blocked_features,
            "config": profile.config
        }
        
        # 2. Merge de Auditoria
        merged_config = merge_policies(all_ordered_layers, profile_static)
        policy_hash = compute_hash(merged_config)
        
        # 3. Mandatory Audit Log (Enterprise Compliance)
        await repo.log_event(
            event_type="POLICY_PREVIEW",
            actor_type="admin",
            actor_id=current_user.email,
            severity="INFO",
            payload={"profile_id": str(profile_id), "hash": policy_hash}
        )

        return {
            "profile_id": profile_id,
            "profile_name": profile.name,
            "layers_applied": [
                {"name": "System Defaults", "priority": -1},
                *[{"name": l["name"], "priority": l["priority"], "scope": l["scope"]} for l in all_ordered_layers],
                {"name": "Profile Static Fallback", "priority": -2}
            ],
            "merged_config": merged_config,
            "hash": policy_hash
        }




@router.post("/devices/{device_id}/state-report")
async def receive_state_report(
    device_id: str,
    report: DeviceStateReport,
):
    """
    Endpoint chamado pelo device para reportar seu estado atual.
    Trigger automático de compliance check.
    """
    from backend.services.drift_detector import evaluate_compliance
    from backend.core.database import async_session_maker
    from backend.models.policy import PolicyState
    from sqlalchemy.future import select

    # P2.0 (Hardenings 5.9.1) - Deduplicação Silenciosa
    async with async_session_maker() as db:
        result = await db.execute(select(PolicyState).where(PolicyState.device_id == device_id))
        ps = result.scalar_one_or_none()
        if ps and ps.state_hash == report.state_hash:
            logger.info(f"📱 [StateReport] device={device_id} ignorado (hash idêntico)")
            return {"status": "ok", "compliance_status": ps.last_compliance_status}

    state_dict = report.model_dump(exclude_none=True)
    logger.info(f"📱 [StateReport] device={device_id}: {list(state_dict.keys())}")

    result = await evaluate_compliance(device_id, reported_state=state_dict)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ═══════════════════════════════════════════════════════════════════════════════

async def _trigger_re_enforcement(policy_id: int) -> None:
    """
    Quando uma policy é atualizada, re-avalia compliance de todos
    os devices vinculados. Desbloqueia failed_loop se a versão mudou.
    """
    from backend.core.database import async_session_maker
    from backend.models.policy import DevicePolicy, PolicyState
    from sqlalchemy.future import select

    async with async_session_maker() as db:
        result = await db.execute(
            select(DevicePolicy.device_id).where(DevicePolicy.policy_id == policy_id)
        )
        device_ids = [row[0] for row in result.all()]

        # Desbloqueia failed_loop para devices afetados
        for did in device_ids:
            state_result = await db.execute(
                select(PolicyState).where(PolicyState.device_id == did)
            )
            state = state_result.scalar_one_or_none()
            if state and state.last_compliance_status == "failed_loop":
                state.last_compliance_status = "non_compliant"
                state.failed_subcommands = []
                state.enforcement_count = 0
                logger.info(f"🔓 [AntiLoop Reset] device={did}: desbloqueado por version bump")
        await db.commit()

    # Re-avalia cada device em background
    from backend.services.drift_detector import evaluate_compliance
    import asyncio
    for did in device_ids:
        asyncio.create_task(evaluate_compliance(did))
