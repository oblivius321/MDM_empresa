"""
Repository para operações com Roles (RBAC).
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, func
from backend.models.role import Role, RoleEnum, role_permissions
from backend.models.permission import Permission
from typing import List, Optional


class RoleRepository:
    """Operações de banco para Roles."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ============================================================================
    # READ OPERATIONS
    # ============================================================================
    
    async def get_by_id(self, role_id: int) -> Optional[Role]:
        """Busca um role por ID com relacionamentos carregados."""
        result = await self.db.execute(
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Optional[Role]:
        """Busca um role por nome exato."""
        result = await self.db.execute(
            select(Role)
            .where(Role.name.ilike(name))
            .options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()
    
    async def get_by_type(self, role_type: RoleEnum) -> Optional[Role]:
        """Busca role pelo tipo (SUPER_ADMIN, ADMIN, etc)."""
        result = await self.db.execute(
            select(Role)
            .where(Role.role_type == role_type)
            .options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()
    
    async def get_all_active(self) -> List[Role]:
        """Retorna todos os roles ativos ordenados por prioridade."""
        result = await self.db.execute(
            select(Role)
            .where(Role.is_active == True)
            .order_by(Role.priority.desc(), Role.name)
            .options(selectinload(Role.permissions))
        )
        return result.scalars().all()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Role]:
        """Retorna todos os roles com paginação."""
        result = await self.db.execute(
            select(Role)
            .order_by(Role.priority.desc(), Role.name)
            .offset(skip)
            .limit(limit)
            .options(selectinload(Role.permissions))
        )
        return result.scalars().all()
    
    async def count_all(self) -> int:
        """Conta total de roles."""
        result = await self.db.execute(select(func.count(Role.id)))
        return result.scalar_one()
    
    async def get_system_roles(self) -> List[Role]:
        """Retorna apenas os roles built-in do sistema."""
        result = await self.db.execute(
            select(Role)
            .where(Role.is_system_role == True)
            .order_by(Role.priority.desc())
            .options(selectinload(Role.permissions))
        )
        return result.scalars().all()
    
    # ============================================================================
    # WRITE OPERATIONS
    # ============================================================================
    
    async def create(
        self,
        name: str,
        role_type: RoleEnum,
        description: Optional[str] = None,
        priority: int = 0,
        created_by_user_id: Optional[int] = None,
        is_system_role: bool = False
    ) -> Role:
        """Cria um novo role."""
        role = Role(
            name=name,
            role_type=role_type,
            description=description,
            priority=priority,
            created_by_user_id=created_by_user_id,
            is_system_role=is_system_role
        )
        self.db.add(role)
        await self.db.flush()
        return role
    
    async def update(
        self,
        role: Role,
        description: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Role:
        """Atualiza um role existente."""
        if description is not None:
            role.description = description
        if is_active is not None:
            role.is_active = is_active
        
        self.db.add(role)
        await self.db.flush()
        return role
    
    async def delete(self, role: Role) -> bool:
        """
        Deleta um role (apenas não-system roles).
        Retorna True se deletado, False se é system role.
        """
        if role.is_system_role:
            return False
        
        await self.db.delete(role)
        await self.db.flush()
        return True
    
    # ============================================================================
    # PERMISSION MANAGEMENT
    # ============================================================================
    
    async def add_permission(self, role: Role, permission: Permission) -> bool:
        """Adiciona uma permissão a um role."""
        if permission not in role.permissions:
            role.permissions.append(permission)
            self.db.add(role)
            await self.db.flush()
            return True
        return False  # Já tinha a permissão
    
    async def remove_permission(self, role: Role, permission: Permission) -> bool:
        """Remove uma permissão de um role."""
        if permission in role.permissions:
            role.permissions.remove(permission)
            self.db.add(role)
            await self.db.flush()
            return True
        return False  # Não tinha a permissão
    
    async def set_permissions(self, role: Role, permissions: List[Permission]) -> Role:
        """Define as permissões de um role (substitui as anteriores)."""
        role.permissions = permissions
        self.db.add(role)
        await self.db.flush()
        return role
    
    async def get_role_permissions(self, role_id: int) -> List[Permission]:
        """Retorna todas as permissões de um role."""
        role = await self.get_by_id(role_id)
        if not role:
            return []
        return role.permissions if role.permissions else []
    
    # ============================================================================
    # BATCH OPERATIONS
    # ============================================================================
    
    async def commit(self):
        """Faz commit de todas as operações pendentes."""
        await self.db.commit()
    
    async def rollback(self):
        """Faz rollback de todas as operações pendentes."""
        await self.db.rollback()
