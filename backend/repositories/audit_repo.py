"""
Repository para operações com Audit Logs.

Auditoria é crítica para segurança. Todos os logs são imutáveis (append-only).
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, desc, func
from backend.models.audit_log import AuditLog, AuditActionEnum
from typing import List, Optional
from datetime import datetime, timedelta


class AuditRepository:
    """Operações de banco para Logs de Auditoria."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ============================================================================
    # READ OPERATIONS (Append-only - sem updates/deletes diretos)
    # ============================================================================
    
    async def get_by_id(self, log_id: int) -> Optional[AuditLog]:
        """Busca um log por ID."""
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.id == log_id)
            .options(selectinload(AuditLog.user))
        )
        return result.scalar_one_or_none()
    
    async def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        days: int = 90
    ) -> List[AuditLog]:
        """Retorna logs de um usuário específico (últimos N dias)."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.created_at >= start_date
                )
            )
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .options(selectinload(AuditLog.user))
        )
        return result.scalars().all()
    
    async def get_by_action(
        self,
        action: AuditActionEnum,
        skip: int = 0,
        limit: int = 100,
        days: int = 90
    ) -> List[AuditLog]:
        """Retorna logs para uma ação específica."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.action == action,
                    AuditLog.created_at >= start_date
                )
            )
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .options(selectinload(AuditLog.user))
        )
        return result.scalars().all()
    
    async def get_by_resource(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        days: int = 90
    ) -> List[AuditLog]:
        """Retorna logs para um recurso específico."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(AuditLog).where(
            and_(
                AuditLog.resource_type == resource_type,
                AuditLog.created_at >= start_date
            )
        )
        
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        
        result = await self.db.execute(
            query
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .options(selectinload(AuditLog.user))
        )
        return result.scalars().all()
    
    async def get_failed_logins(
        self,
        skip: int = 0,
        limit: int = 100,
        hours: int = 24
    ) -> List[AuditLog]:
        """Retorna tentativas de login falhadas recentes."""
        start_date = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.action == AuditActionEnum.FAILED_LOGIN,
                    AuditLog.created_at >= start_date
                )
            )
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .options(selectinload(AuditLog.user))
        )
        return result.scalars().all()
    
    async def get_privilege_escalation_attempts(
        self,
        skip: int = 0,
        limit: int = 100,
        days: int = 30
    ) -> List[AuditLog]:
        """Retorna tentativas de escalação de privilégio."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.action == AuditActionEnum.PRIVILEGE_ESCALATION_ATTEMPT,
                    AuditLog.created_at >= start_date
                )
            )
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .options(selectinload(AuditLog.user))
        )
        return result.scalars().all()
    
    async def get_critical_actions(
        self,
        skip: int = 0,
        limit: int = 100,
        days: int = 30
    ) -> List[AuditLog]:
        """Retorna ações críticas (wipe, lock, delete_logs, etc)."""
        critical_actions = [
            AuditActionEnum.DEVICE_WIPE,
            AuditActionEnum.DEVICE_LOCK,
            AuditActionEnum.AUDIT_LOG_DELETE,
            AuditActionEnum.USER_DELETE,
            AuditActionEnum.ROLE_ASSIGN
        ]
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.action.in_(critical_actions),
                    AuditLog.created_at >= start_date
                )
            )
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .options(selectinload(AuditLog.user))
        )
        return result.scalars().all()
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        days: int = 90
    ) -> List[AuditLog]:
        """Retorna todos os logs (com limite de dias para performance)."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.created_at >= start_date)
            .order_by(desc(AuditLog.created_at))
            .offset(skip)
            .limit(limit)
            .options(selectinload(AuditLog.user))
        )
        return result.scalars().all()
    
    async def count_by_action(
        self,
        action: AuditActionEnum,
        days: int = 90
    ) -> int:
        """Conta quantas vezes uma ação ocorreu."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.action == action,
                    AuditLog.created_at >= start_date
                )
            )
        )
        return result.scalar_one()
    
    async def count_all(self, days: int = 90) -> int:
        """Conta total de logs."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.created_at >= start_date
            )
        )
        return result.scalar_one()
    
    # ============================================================================
    # WRITE OPERATIONS (Append-only)
    # ============================================================================
    
    async def create(
        self,
        action: AuditActionEnum,
        resource_type: str,
        user_id: Optional[int] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        is_success: bool = True,
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Cria um novo log de auditoria (append-only)."""
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            is_success=is_success,
            error_message=error_message
        )
        self.db.add(log)
        await self.db.flush()
        return log
    
    async def log_user_action(
        self,
        user_id: int,
        action: AuditActionEnum,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        is_success: bool = True,
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Helper para logar uma ação de usuário."""
        return await self.create(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            is_success=is_success,
            error_message=error_message
        )
    
    async def commit(self):
        """Faz commit de todos os logs pendentes."""
        await self.db.commit()
    
    # ============================================================================
    # RETENTION POLICY (Cleanup automático)
    # ============================================================================
    
    async def cleanup_old_logs(self, days_to_keep: int = 365) -> int:
        """
        Remove logs mais antigos que N dias (política de retenção).
        Deve ser executado periodicamente.
        
        IMPORTANTE: Logs de ações críticas (WIPE, DELETE, etc) devem ser
        preservados por mais tempo (ex: 7 anos) para compliance.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Critical actions to preserve longer
        critical_actions = [
            AuditActionEnum.DEVICE_WIPE,
            AuditActionEnum.AUDIT_LOG_DELETE,
            AuditActionEnum.USER_DELETE,
        ]
        
        # Deletar apenas logs não-críticos antigos
        result = await self.db.execute(
            select(AuditLog).where(
                and_(
                    AuditLog.created_at < cutoff_date,
                    ~AuditLog.action.in_(critical_actions)
                )
            )
        )
        
        logs_to_delete = result.scalars().all()
        deleted_count = len(logs_to_delete)
        
        for log in logs_to_delete:
            await self.db.delete(log)
        
        await self.db.flush()
        return deleted_count
