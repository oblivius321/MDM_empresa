"""
Service de RBAC (Role-Based Access Control).

Lógica de negócio para gerenciar roles, permissões e validações
de segurança contra privilege escalation.
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.models.role import Role, RoleEnum
from backend.models.permission import Permission
from backend.repositories.role_repo import RoleRepository
from backend.repositories.permission_repo import PermissionRepository
from backend.repositories.audit_repo import AuditRepository
from backend.repositories.user_repo import UserRepository
from backend.models.audit_log import AuditActionEnum
from backend.utils.rbac_constants import (
    RoleDefinition,
    PERMISSIONS,
    SUPER_ADMIN_ONLY_PERMISSIONS,
    MFA_REQUIRED_ACTIONS,
    CRITICAL_AUDIT_ACTIONS,
)
from typing import List, Optional


class RBACService:
    """Serviço de lógica de RBAC."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.role_repo = RoleRepository(db)
        self.permission_repo = PermissionRepository(db)
        self.audit_repo = AuditRepository(db)
        self.user_repo = UserRepository(db)
    
    # ============================================================================
    # INICIALIZAÇÃO (SEED)
    # ============================================================================
    
    async def initialize_rbac(self):
        """
        Inicializa o sistema RBAC com roles e permissões padrão.
        Executado na primeira inicialização do sistema.
        
        IMPORTANTE: Idempotente - pode ser executado múltiplas vezes com segurança.
        """
        try:
            # Passo 1: Criar todas as permissões
            permissions_dict = {}
            for perm_name, resource, action, is_critical, requires_mfa in PERMISSIONS:
                existing = await self.permission_repo.get_by_name(perm_name)
                if not existing:
                    perm = await self.permission_repo.create(
                        name=perm_name,
                        resource=resource,
                        action=action,
                        is_critical=is_critical,
                        requires_mfa=requires_mfa,
                        is_system_permission=True
                    )
                    permissions_dict[perm_name] = perm
                else:
                    permissions_dict[perm_name] = existing
            
            # Passo 2: Criar roles com suas permissões
            for role_enum in RoleEnum:
                role_def = RoleDefinition[role_enum.name].value
                
                existing_role = await self.role_repo.get_by_type(role_enum)
                if not existing_role:
                    # Coletar as permissões deste role
                    role_permissions = [
                        permissions_dict[perm_name]
                        for perm_name in role_def["permissions"]
                        if perm_name in permissions_dict
                    ]
                    
                    # Criar o role
                    role = await self.role_repo.create(
                        name=role_def["name"],
                        role_type=role_enum,
                        description=role_def["description"],
                        priority=role_def["priority"],
                        is_system_role=True,
                        created_by_user_id=None
                    )
                    
                    # Atribuir permissões
                    await self.role_repo.set_permissions(role, role_permissions)
            
            await self.role_repo.commit()
            print("✅ RBAC initialized successfully")
            
        except Exception as e:
            await self.role_repo.rollback()
            print(f"❌ RBAC initialization failed: {e}")
            raise
    
    # ============================================================================
    # VALIDAÇÕES DE SEGURANÇA
    # ============================================================================
    
    async def can_user_manage_roles(self, current_user: User) -> bool:
        """Verifica se user pode gerenciar roles."""
        if not current_user.roles:
            return False
        
        # Apenas SUPER_ADMIN e ADMIN podem gerenciar
        role_types = {role.role_type for role in current_user.roles}
        return RoleEnum.SUPER_ADMIN in role_types or RoleEnum.ADMIN in role_types
    
    async def can_user_perform_action(
        self,
        current_user: User,
        action: str,
        require_mfa: bool = False
    ) -> bool:
        """
        Verifica se usuário tem permissão para uma ação específica.
        
        Args:
            current_user: Usuário autenticado
            action: Nome da permissão (ex: "devices:wipe")
            require_mfa: Se essa ação requer MFA (será verificado pelo middleware)
        
        Retorna: True se pode executar, False caso contrário
        """
        if not current_user.is_active:
            return False
        
        # Carregar roles se não estiver carregado
        if not current_user.roles:
            user = await self.user_repo.get_by_id(current_user.id)
            if not user:
                return False
            current_user = user
        
        return current_user.has_permission(action)
    
    async def check_privilege_escalation(
        self,
        current_user: User,
        target_role: Role,
        action: str = "assign"
    ) -> tuple[bool, Optional[str]]:
        """
        Verifica se uma atribuição de role tentaria escalar privilégios.
        
        Regras de segurança:
        1. ADMIN não pode criar/atribuir SUPER_ADMIN
        2. Não pode atribuir role que ele próprio não tem
        3. Não pode remover o último SUPER_ADMIN do sistema
        4. ADMIN não pode deletar permissões
        
        Retorna: (is_valid, error_message or None)
        """
        user_highest_priority = current_user.highest_role_priority if current_user.roles else 0
        target_priority = target_role.priority if target_role else 0
        
        # ❌ Regra 1: Impedir atribuição de role que user não tem
        if action == "assign":
            # User só pode atribuir roles que ele próprio tem ou prioridade menor
            if target_priority > user_highest_priority:
                return False, f"Você não pode atribuir {target_role.name} porque não o possui"
            
            # ❌ Regra 2: ADMIN não pode criar SUPER_ADMIN
            user_roles = {role.role_type for role in current_user.roles}
            if RoleEnum.SUPER_ADMIN not in user_roles:
                if target_role.role_type == RoleEnum.SUPER_ADMIN:
                    # Log tentativa de escalação
                    await self.audit_repo.create(
                        action=AuditActionEnum.PRIVILEGE_ESCALATION_ATTEMPT,
                        user_id=current_user.id,
                        resource_type="roles",
                        resource_id=str(target_role.id),
                        details={"attempted_role": target_role.name},
                        is_success=False,
                        error_message=f"User {current_user.email} attempted to create SUPER_ADMIN"
                    )
                    await self.audit_repo.commit()
                    return False, "Você não pode criar ou atribuir SUPER_ADMIN"
        
        # ❌ Regra 3: Proteger último SUPER_ADMIN
        if action == "revoke" and target_role.role_type == RoleEnum.SUPER_ADMIN:
            super_admins = await self.role_repo.get_by_type(RoleEnum.SUPER_ADMIN)
            if super_admins and len(super_admins.users or []) <= 1:
                return False, "Não pode remover o último SUPER_ADMIN do sistema"
        
        return True, None
    
    # ============================================================================
    # GERENCIAMENTO DE ROLES
    # ============================================================================
    
    async def assign_role_to_user(
        self,
        current_user: User,
        target_user: User,
        role: Role,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Atribui um role a um usuário com validações de segurança.
        
        Retorna: (success, error_message or None)
        """
        # Validar permissão de quem está atribuindo
        if not await self.can_user_perform_action(current_user, "roles:assign"):
            # Log tentativa
            await self.audit_repo.create(
                action=AuditActionEnum.PERMISSION_DENIED,
                user_id=current_user.id,
                resource_type="roles",
                resource_id=str(role.id),
                details={"target_user": target_user.email, "action_attempted": "roles:assign"},
                ip_address=ip_address,
                is_success=False,
                error_message=f"Permission denied"
            )
            await self.audit_repo.commit()
            return False, "Você não tem permissão para atribuir roles"
        
        # Verificar privilege escalation
        is_valid, error = await self.check_privilege_escalation(
            current_user,
            role,
            action="assign"
        )
        if not is_valid:
            return False, error
        
        # Executar atribuição
        if role not in target_user.roles:
            target_user.roles.append(role)
            await self.user_repo.update(target_user)
            
            # Auditar
            await self.audit_repo.create(
                action=AuditActionEnum.ROLE_ASSIGN,
                user_id=current_user.id,
                resource_type="users",
                resource_id=str(target_user.id),
                details={
                    "target_user": target_user.email,
                    "assigned_role": role.name,
                    "role_type": role.role_type.value
                },
                ip_address=ip_address,
                user_agent=user_agent,
                is_success=True
            )
            await self.audit_repo.commit()
            return True, None
        
        return False, f"Usuário já possui o role {role.name}"
    
    async def revoke_role_from_user(
        self,
        current_user: User,
        target_user: User,
        role: Role,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Remove um role de um usuário com validações de segurança.
        
        Retorna: (success, error_message or None)
        """
        # Validar permissão
        if not await self.can_user_perform_action(current_user, "roles:revoke"):
            # Log tentativa
            await self.audit_repo.create(
                action=AuditActionEnum.PERMISSION_DENIED,
                user_id=current_user.id,
                resource_type="roles",
                resource_id=str(role.id),
                details={"target_user": target_user.email, "action_attempted": "roles:revoke"},
                ip_address=ip_address,
                is_success=False
            )
            await self.audit_repo.commit()
            return False, "Você não tem permissão para remover roles"
        
        # Verificar privilege escalation
        is_valid, error = await self.check_privilege_escalation(
            current_user,
            role,
            action="revoke"
        )
        if not is_valid:
            return False, error
        
        # Executar revoke
        if role in target_user.roles:
            target_user.roles.remove(role)
            await self.user_repo.update(target_user)
            
            # Auditar
            await self.audit_repo.create(
                action=AuditActionEnum.ROLE_REVOKE,
                user_id=current_user.id,
                resource_type="users",
                resource_id=str(target_user.id),
                details={
                    "target_user": target_user.email,
                    "revoked_role": role.name,
                    "role_type": role.role_type.value
                },
                ip_address=ip_address,
                user_agent=user_agent,
                is_success=True
            )
            await self.audit_repo.commit()
            return True, None
        
        return False, f"Usuário não possui o role {role.name}"
    
    # ============================================================================
    # HELPERS
    # ============================================================================
    
    async def get_user_permissions(self, user_id: int) -> set:
        """Retorna todas as permissões de um usuário."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return set()
        return user.all_permissions
    
    async def requires_action_confirmation(self, action: str) -> bool:
        """Verifica se uma ação requer confirmação adicional (2FA)."""
        return action in MFA_REQUIRED_ACTIONS
    
    async def is_critical_audit_action(self, action: str) -> bool:
        """Verifica se uma ação requer auditoriae detalhada."""
        return action in CRITICAL_AUDIT_ACTIONS
