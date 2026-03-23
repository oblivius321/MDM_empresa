"""
Repository para operações com Permissions.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, func
from backend.models.permission import Permission
from typing import List, Optional


class PermissionRepository:
    """Operações de banco para Permissions."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ============================================================================
    # READ OPERATIONS
    # ============================================================================
    
    async def get_by_id(self, permission_id: int) -> Optional[Permission]:
        """Busca uma permissão por ID."""
        result = await self.db.execute(
            select(Permission).where(Permission.id == permission_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Optional[Permission]:
        """Busca uma permissão por nome exato."""
        result = await self.db.execute(
            select(Permission).where(Permission.name.ilike(name))
        )
        return result.scalar_one_or_none()
    
    async def get_by_resource_action(self, resource: str, action: str) -> Optional[Permission]:
        """Busca uma permissão por resource + action."""
        result = await self.db.execute(
            select(Permission).where(
                and_(
                    Permission.resource.ilike(resource),
                    Permission.action.ilike(action)
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_resource(self, resource: str) -> List[Permission]:
        """Busca todas as permissões de um recurso."""
        result = await self.db.execute(
            select(Permission)
            .where(Permission.resource.ilike(resource))
            .order_by(Permission.action)
        )
        return result.scalars().all()
    
    async def get_all_active(self) -> List[Permission]:
        """Retorna todas as permissões ativas."""
        result = await self.db.execute(
            select(Permission)
            .where(Permission.is_active == True)
            .order_by(Permission.resource, Permission.action)
        )
        return result.scalars().all()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Permission]:
        """Retorna todas as permissões com paginação."""
        result = await self.db.execute(
            select(Permission)
            .order_by(Permission.resource, Permission.action)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def count_all(self) -> int:
        """Conta total de permissões."""
        result = await self.db.execute(select(func.count(Permission.id)))
        return result.scalar_one()
    
    async def get_critical_permissions(self) -> List[Permission]:
        """Retorna apenas as permissões críticas (requerem logs detalhados)."""
        result = await self.db.execute(
            select(Permission)
            .where(Permission.is_critical == True)
            .order_by(Permission.resource)
        )
        return result.scalars().all()
    
    async def get_mfa_required_permissions(self) -> List[Permission]:
        """Retorna permissões que requerem MFA."""
        result = await self.db.execute(
            select(Permission)
            .where(Permission.requires_mfa == True)
            .order_by(Permission.resource)
        )
        return result.scalars().all()
    
    # ============================================================================
    # WRITE OPERATIONS
    # ============================================================================
    
    async def create(
        self,
        name: str,
        resource: str,
        action: str,
        description: Optional[str] = None,
        is_critical: bool = False,
        requires_mfa: bool = False,
        is_system_permission: bool = True
    ) -> Permission:
        """Cria uma nova permissão."""
        permission = Permission(
            name=name,
            resource=resource,
            action=action,
            description=description,
            is_critical=is_critical,
            requires_mfa=requires_mfa,
            is_system_permission=is_system_permission
        )
        self.db.add(permission)
        await self.db.flush()
        return permission
    
    async def update(
        self,
        permission: Permission,
        description: Optional[str] = None,
        is_critical: Optional[bool] = None,
        requires_mfa: Optional[bool] = None,
        is_active: Optional[bool] = None
    ) -> Permission:
        """Atualiza uma permissão existente."""
        if description is not None:
            permission.description = description
        if is_critical is not None:
            permission.is_critical = is_critical
        if requires_mfa is not None:
            permission.requires_mfa = requires_mfa
        if is_active is not None:
            permission.is_active = is_active
        
        self.db.add(permission)
        await self.db.flush()
        return permission
    
    async def delete(self, permission: Permission) -> bool:
        """
        Deleta uma permissão (apenas não-system).
        Retorna True se deletado, False se é system permission.
        """
        if permission.is_system_permission:
            return False
        
        await self.db.delete(permission)
        await self.db.flush()
        return True
    
    # ============================================================================
    # BATCH OPERATIONS
    # ============================================================================
    
    async def commit(self):
        """Faz commit de todas as operações."""
        await self.db.commit()
    
    async def rollback(self):
        """Faz rollback de todas as operações."""
        await self.db.rollback()
