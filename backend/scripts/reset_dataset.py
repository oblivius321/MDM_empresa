import asyncio
import uuid
import logging
from sqlalchemy import text
from backend.core.database import engine, Base, async_session_maker
from backend.core.security import get_password_hash
from backend.models.user import User
from backend.models.device import Device
from backend.models.policy import ProvisioningProfile, DevicePolicy, DeviceCommand
from backend.models.telemetry import DeviceTelemetry
from backend.models.audit_log import AuditLog
from backend.models.role import Role, RoleEnum
from backend.models.permission import Permission

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset_db")

async def reset_db():
    logger.info("🚀 Iniciando RESET CONTROLADO do Banco de Dados (SaaS Re-arch)...")
    
    async with engine.begin() as conn:
        # 1. Drop all tables
        logger.info("🗑️ Removendo todas as tabelas existentes para garantir consistência...")
        await conn.run_sync(Base.metadata.drop_all)
        
        # 2. Create all tables
        logger.info("🏗️ Criando novas tabelas baseadas na arquitetura de 3 camadas...")
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ Esquema do banco de dados atualizado com sucesso.")

    logger.info("🌱 Semeando dados iniciais (Seed Data)...")
    async with async_session_maker() as session:
        # A. Criar Admin Padrão
        admin_user = User(
            email="admin@elion.com.br",
            hashed_password=get_password_hash("admin123"),
            is_admin=True,
            is_active=True,
            security_question="PET",
            security_answer_hash=get_password_hash("rex")
        )
        session.add(admin_user)
        
        # B. Criar Provisioning Profile Padrão (Essencial para Enrollment)
        # ID fixo para facilitar o teste do QR Code inicial
        default_profile_id = uuid.UUID("d1e57c8a-7b2a-4f9e-bc8d-0e1f2a3b4c5d")
        default_profile = ProvisioningProfile(
            id=default_profile_id,
            name="Perfil Padrão (Full Kiosk)",
            kiosk_enabled=True,
            allowed_apps=["com.android.settings", "com.elion.mdm"],
            blocked_features={
                "DISALLOW_SAFE_BOOT": False,
                "DISALLOW_FACTORY_RESET": False,
                "DISALLOW_DEBUGGING_FEATURES": True,
                "STATUS_BAR_DISABLED": True
            },
            config={
                "wifi_ssid": "Elion_Corp",
                "heartbeat_interval_seconds": 60,
                "kiosk_package": "com.elion.mdm"
            },
            version=1,
            is_active=True
        )
        session.add(default_profile)
        
        # C. Criar Roles Básicos
        super_admin_role = Role(
            name="Super Administrador",
            role_type=RoleEnum.SUPER_ADMIN,
            priority=1000,
            is_system_role=True
        )
        session.add(super_admin_role)
        
        # D. Registro de Auditoria do Seed
        seed_log = AuditLog(
            event_type="SYSTEM_SEED",
            actor_type="system",
            actor_id="bootstrap_script",
            severity="INFO",
            payload={"message": "Banco de dados reinicializado e semeado com sucesso."}
        )
        session.add(seed_log)
        
        await session.commit()
        
        logger.info("--------------------------------------------------")
        logger.info("✨ SEED CONCLUÍDO COM SUCESSO!")
        logger.info(f"👤 Admin: admin@elion.com.br / admin123")
        logger.info(f"📋 Profile ID para QR Code: {default_profile_id}")
        logger.info(f"🔗 Nome do Profile: {default_profile.name}")
        logger.info("--------------------------------------------------")

if __name__ == "__main__":
    asyncio.run(reset_db())
