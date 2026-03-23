"""
Endpoints para gerenciamento de RBAC (Roles, Permissions, Auditoria).

Endpoints:
- GET  /api/rbac/roles                    - Listar roles
- GET  /api/rbac/roles/{role_id}          - Detalhes role
- POST /api/rbac/roles                    - Criar role
- PUT  /api/rbac/roles/{role_id}          - Atualizar role
- DELETE /api/rbac/roles/{role_id}        - Deletar role

- GET  /api/rbac/permissions              - Listar permissões
- GET  /api/rbac/permissions/{perm_id}    - Detalhes permissão
- POST /api/rbac/permissions              - Criar permissão

- POST /api/rbac/roles/{role_id}/permissions/{perm_id}    - Adicionar permissão a role
- DELETE /api/rbac/roles/{role_id}/permissions/{perm_id}  - Remover permissão

- POST /api/rbac/users/{user_id}/roles/{role_id}   - Atribuir role a user
- DELETE /api/rbac/users/{user_id}/roles/{role_id} - Remover role de user

- GET  /api/rbac/users/{user_id}/permissions      - Listar permissões de user

- GET /api/rbac/audit                     - Listar logs de auditoria
- GET /api/rbac/audit/critical            - Logs críticos
- GET /api/rbac/audit/user/{user_id}      - Logs de um usuário
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.api.auth import get_current_user
from backend.models.user import User
from backend.repositories.role_repo import RoleRepository
from backend.repositories.permission_repo import PermissionRepository
from backend.repositories.audit_repo import AuditRepository
from backend.repositories.user_repo import UserRepository
from backend.services.rbac_service import RBACService
from backend.schemas.role import (
    RoleCreate, RoleUpdate, RoleResponse, RoleDetailedResponse,
    UserRoleAssign, UserRoleRevoke, PermissionBase
)
from backend.schemas.permission import PermissionCreate, PermissionResponse, PermissionListResponse
from backend.schemas.audit_log import AuditLogResponse, AuditLogListResponse
from backend.models.audit_log import AuditActionEnum
from backend.models.role import RoleEnum
from backend.utils.decorators import PermissionChecker
from backend.core.limiter import limiter
from typing import List

router = APIRouter(prefix="/rbac", tags=["RBAC"])


# ============================================================================
# ROLE ENDPOINTS
# ============================================================================

@router.get("/roles", response_model=List[RoleResponse])
@limiter.limit("100/minute")
async def list_roles(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista todos os roles (apenas VIEWER+)."""
    checker = PermissionChecker(current_user)
    checker.assert_permission("roles:read")
    
    repo = RoleRepository(db)
    roles = await repo.get_all(skip=skip, limit=limit)
    return roles


@router.get("/roles/{role_id}", response_model=RoleDetailedResponse)
@limiter.limit("100/minute")
async def get_role(
    request: Request,
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna detalhes de um role."""
    checker = PermissionChecker(current_user)
    checker.assert_permission("roles:read")
    
    repo = RoleRepository(db)
    role = await repo.get_by_id(role_id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role não encontrado"
        )
    
    return role


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("50/minute")
async def create_role(
    request: Request,
    role_data: RoleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cria um novo role.
    
    ⚠️ APENAS SUPER_ADMIN pode criar roles.
    """
    checker = PermissionChecker(current_user)
    checker.assert_permission("roles:create")
    checker.assert_role("SUPER_ADMIN")
    
    repo = RoleRepository(db)
    
    # Verificar se nome já existe
    existing = await repo.get_by_name(role_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role com esse nome já existe"
        )
    
    # Criar role
    role = await repo.create(
        name=role_data.name,
        role_type=role_data.role_type,
        description=role_data.description,
        created_by_user_id=current_user.id,
        is_system_role=False
    )
    
    await repo.commit()
    
    # Auditar
    audit_repo = AuditRepository(db)
    await audit_repo.create(
        action=AuditActionEnum.ROLE_CREATE,
        user_id=current_user.id,
        resource_type="roles",
        resource_id=str(role.id),
        details={"name": role.name, "type": role.role_type.value},
        ip_address=request.client.host if request.client else None,
        is_success=True
    )
    await audit_repo.commit()
    
    return role


@router.put("/roles/{role_id}", response_model=RoleResponse)
@limiter.limit("50/minute")
async def update_role(
    request: Request,
    role_id: int,
    role_data: RoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Atualiza um role.
    
    ⚠️ Apenas SUPER_ADMIN, e não pode atualizar system roles.
    """
    checker = PermissionChecker(current_user)
    checker.assert_permission("roles:update")
    checker.assert_role("SUPER_ADMIN")
    
    repo = RoleRepository(db)
    role = await repo.get_by_id(role_id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role não encontrado"
        )
    
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não pode atualizar system roles"
        )
    
    # Atualizar
    role = await repo.update(
        role,
        description=role_data.description,
        is_active=role_data.is_active
    )
    
    await repo.commit()
    
    return role


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("50/minute")
async def delete_role(
    request: Request,
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deleta um role.
    
    ⚠️ Apenas SUPER_ADMIN, e não pode deletar system roles.
    """
    checker = PermissionChecker(current_user)
    checker.assert_permission("roles:delete")
    checker.assert_role("SUPER_ADMIN")
    
    repo = RoleRepository(db)
    role = await repo.get_by_id(role_id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role não encontrado"
        )
    
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não pode deletar system roles"
        )
    
    deleted = await repo.delete(role)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não foi possível deletar role"
        )
    
    await repo.commit()
    
    return None


# ============================================================================
# PERMISSION ENDPOINTS
# ============================================================================

@router.get("/permissions", response_model=PermissionListResponse)
@limiter.limit("100/minute")
async def list_permissions(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista todas as permissões."""
    checker = PermissionChecker(current_user)
    checker.assert_permission("permissions:read")
    
    repo = PermissionRepository(db)
    permissions = await repo.get_all(skip=skip, limit=limit)
    total = await repo.count_all()
    
    return PermissionListResponse(
        total=total,
        permissions=permissions
    )


@router.get("/permissions/{perm_id}", response_model=PermissionResponse)
@limiter.limit("100/minute")
async def get_permission(
    request: Request,
    perm_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna detalhes de uma permissão."""
    checker = PermissionChecker(current_user)
    checker.assert_permission("permissions:read")
    
    repo = PermissionRepository(db)
    permission = await repo.get_by_id(perm_id)
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permissão não encontrada"
        )
    
    return permission


# ============================================================================
# ROLE-PERMISSION MANAGEMENT
# ============================================================================

@router.post("/roles/{role_id}/permissions/{perm_id}", status_code=status.HTTP_200_OK)
@limiter.limit("50/minute")
async def add_permission_to_role(
    request: Request,
    role_id: int,
    perm_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Adiciona uma permissão a um role."""
    checker = PermissionChecker(current_user)
    checker.assert_role("SUPER_ADMIN")
    
    role_repo = RoleRepository(db)
    perm_repo = PermissionRepository(db)
    
    role = await role_repo.get_by_id(role_id)
    permission = await perm_repo.get_by_id(perm_id)
    
    if not role or not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role ou Permission não encontrado"
        )
    
    success = await role_repo.add_permission(role, permission)
    await role_repo.commit()
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role já possui essa permissão"
        )
    
    return {"message": "Permissão adicionada com sucesso"}


@router.delete("/roles/{role_id}/permissions/{perm_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("50/minute")
async def remove_permission_from_role(
    request: Request,
    role_id: int,
    perm_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove uma permissão de um role."""
    checker = PermissionChecker(current_user)
    checker.assert_role("SUPER_ADMIN")
    
    role_repo = RoleRepository(db)
    perm_repo = PermissionRepository(db)
    
    role = await role_repo.get_by_id(role_id)
    permission = await perm_repo.get_by_id(perm_id)
    
    if not role or not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role ou Permission não encontrado"
        )
    
    success = await role_repo.remove_permission(role, permission)
    await role_repo.commit()
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role não possui essa permissão"
        )
    
    return None


# ============================================================================
# USER-ROLE MANAGEMENT
# ============================================================================

@router.post("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_200_OK)
@limiter.limit("50/minute")
async def assign_role_to_user(
    request: Request,
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Atribui um role a um usuário."""
    checker = PermissionChecker(current_user)
    checker.assert_permission("roles:assign")
    
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    rbac_service = RBACService(db)
    
    target_user = await user_repo.get_by_id(user_id)
    role = await role_repo.get_by_id(role_id)
    
    if not target_user or not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário ou Role não encontrado"
        )
    
    # Usar serviço com validações de segurança
    success, error = await rbac_service.assign_role_to_user(
        current_user=current_user,
        target_user=target_user,
        role=role,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Não foi possível atribuir role"
        )
    
    return {"message": "Role atribuído com sucesso"}


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("50/minute")
async def revoke_role_from_user(
    request: Request,
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove um role de um usuário."""
    checker = PermissionChecker(current_user)
    checker.assert_permission("roles:revoke")
    
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    rbac_service = RBACService(db)
    
    target_user = await user_repo.get_by_id(user_id)
    role = await role_repo.get_by_id(role_id)
    
    if not target_user or not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário ou Role não encontrado"
        )
    
    # Usar serviço com validações de segurança
    success, error = await rbac_service.revoke_role_from_user(
        current_user=current_user,
        target_user=target_user,
        role=role,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Não foi possível remover role"
        )
    
    return None


@router.get("/users/{user_id}/permissions", response_model=List[str])
@limiter.limit("100/minute")
async def get_user_permissions(
    request: Request,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retorna todas as permissões de um usuário."""
    checker = PermissionChecker(current_user)
    checker.assert_permission("users:read")
    
    # Só admin+ pode ver permissões de outros, user vê a si mesmo
    if current_user.id != user_id:
        checker.assert_permission("users:read")
    
    rbac_service = RBACService(db)
    permissions = await rbac_service.get_user_permissions(user_id)
    
    return sorted(list(permissions))


# ============================================================================
# AUDIT LOG ENDPOINTS
# ============================================================================

@router.get("/audit", response_model=AuditLogListResponse)
@limiter.limit("100/minute")
async def list_audit_logs(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: int = Query(None),
    action: str = Query(None),
    days: int = Query(90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista logs de auditoria (com filtros).
    
    ⚠️ VIEWER+: Can view, SUPER_ADMIN: pode deletar
    """
    checker = PermissionChecker(current_user)
    checker.assert_permission("audit:read")
    
    audit_repo = AuditRepository(db)
    
    # Filtro por usuário
    if user_id:
        logs = await audit_repo.get_by_user(user_id, skip=skip, limit=limit, days=days)
        total = await audit_repo.count_by_action(AuditActionEnum.LOGIN, days=days) if action else await audit_repo.count_all(days=days)
    elif action:
        try:
            action_enum = AuditActionEnum[action]
            logs = await audit_repo.get_by_action(action_enum, skip=skip, limit=limit, days=days)
            total = await audit_repo.count_by_action(action_enum, days=days)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ação desconhecida: {action}"
            )
    else:
        logs = await audit_repo.get_all(skip=skip, limit=limit, days=days)
        total = await audit_repo.count_all(days=days)
    
    return AuditLogListResponse(
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        logs=[
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                user_email=log.user.email if log.user else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                is_success=log.is_success,
                error_message=log.error_message,
                created_at=log.created_at
            )
            for log in logs
        ]
    )


@router.get("/audit/critical", response_model=AuditLogListResponse)
@limiter.limit("100/minute")
async def list_critical_audit_logs(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista apenas ações críticas (wipe, delete, etc).
    
    Acessível apenas para ADMIN+.
    """
    checker = PermissionChecker(current_user)
    checker.assert_permission("audit:read")
    checker.assert_any_permission("roles:ADMIN", "roles:SUPER_ADMIN")  # ADMIN+
    
    audit_repo = AuditRepository(db)
    logs = await audit_repo.get_critical_actions(skip=skip, limit=limit, days=days)
    total = len(logs)  # TODO: Implementar count adequado
    
    return AuditLogListResponse(
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        logs=[
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                user_email=log.user.email if log.user else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                is_success=log.is_success,
                error_message=log.error_message,
                created_at=log.created_at
            )
            for log in logs
        ]
    )


@router.delete("/audit/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_audit_log(
    request: Request,
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deleta um log de auditoria.
    
    ⚠️ APENAS SUPER_ADMIN pode deletar logs.
    CRÍTICO: Cada deleção de log é auditada.
    """
    checker = PermissionChecker(current_user)
    checker.assert_permission("audit:delete")
    checker.assert_role("SUPER_ADMIN")
    
    audit_repo = AuditRepository(db)
    log = await audit_repo.get_by_id(log_id)
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log não encontrado"
        )
    
    # Auditar a deleção do log
    await audit_repo.create(
        action=AuditActionEnum.AUDIT_LOG_DELETE,
        user_id=current_user.id,
        resource_type="audit_logs",
        resource_id=str(log_id),
        details={
            "deleted_log_action": log.action.value,
            "deleted_log_resource": log.resource_type,
            "deleted_log_user": log.user_id
        },
        ip_address=request.client.host if request.client else None,
        is_success=True
    )
    
    # Deletar o log
    await audit_repo.db.delete(log)
    await audit_repo.commit()
    
    return None
