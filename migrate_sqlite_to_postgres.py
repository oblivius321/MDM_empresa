"""
Script de Migração SQLite → PostgreSQL para Elion MDM
Migra dados de mdm_database.db para PostgreSQL com segurança e validação
"""
import asyncio
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, select, insert
from backend.core.database import Base
from backend.models.user import User
from backend.models.device import Device
from backend.models.policy import Policy, CommandQueue, Log
from backend.models.telemetry import DeviceTelemetry
from backend.core.security import get_password_hash

# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Database URLs
SQLITE_PATH = Path(__file__).resolve().parent / "mdm_database.db"
POSTGRES_URL = os.getenv("DATABASE_URL")
if not POSTGRES_URL:
    raise ValueError("DATABASE_URL não configurado. Configure em .env ou .env.development")
SQLITE_URL = f"sqlite+aiosqlite:///{SQLITE_PATH}"

async def create_postgres_database():
    """Cria o banco de dados PostgreSQL se não existir"""
    # Extract database name from URL
    db_url_parts = POSTGRES_URL.split('/')
    db_name = db_url_parts[-1]
    server_url = '/'.join(db_url_parts[:-1]) + '/postgres'
    
    print(f"✓ Criando banco de dados '{db_name}' no PostgreSQL...")
    
    try:
        engine = create_async_engine(server_url, isolation_level="AUTOCOMMIT")
        async with engine.begin() as conn:
            # Check if database exists
            result = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
            db_exists = result.fetchone() is not None
            
            if not db_exists:
                await conn.execute(text(f"CREATE DATABASE {db_name}"))
                print(f"  ✓ Banco de dados '{db_name}' criado com sucesso")
            else:
                print(f"  ✓ Banco de dados '{db_name}' já existe")
        
        await engine.dispose()
    except Exception as e:
        print(f"  ⚠ Erro ao criar banco: {e}")
        raise

async def init_postgres_schema():
    """Cria o schema no PostgreSQL"""
    print("✓ Criando schema no PostgreSQL...")
    
    engine = create_async_engine(POSTGRES_URL, echo=False)
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("  ✓ Schema criado com sucesso")
    except Exception as e:
        print(f"  ⚠ Erro ao criar schema: {e}")
        raise
    finally:
        await engine.dispose()

async def migrate_users():
    """Migra usuários do SQLite para PostgreSQL"""
    print("✓ Migrando usuários...")
    
    # Read from SQLite
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, hashed_password, is_admin, is_active FROM users")
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            print("  ✓ Nenhum usuário para migrar")
            return
        
        # Write to PostgreSQL
        engine = create_async_engine(POSTGRES_URL)
        session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with session_maker() as session:
            for user_id, email, hashed_password, is_admin, is_active in users:
                user = User(
                    id=user_id,
                    email=email,
                    hashed_password=hashed_password,
                    is_admin=bool(is_admin),
                    is_active=bool(is_active)
                )
                session.add(user)
            
            await session.commit()
            print(f"  ✓ {len(users)} usuários migrados")
        
        await engine.dispose()
    except sqlite3.OperationalError:
        print("  ✓ Tabela 'users' não encontrada (primeira execução)")

async def migrate_devices():
    """Migra dispositivos do SQLite para PostgreSQL"""
    print("✓ Migrando dispositivos...")
    
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_id, name, device_type, imei, model, android_version, 
                   company, status, last_checkin, enrollment_date, is_active 
            FROM devices
        """)
        devices = cursor.fetchall()
        conn.close()
        
        if not devices:
            print("  ✓ Nenhum dispositivo para migrar")
            return
        
        engine = create_async_engine(POSTGRES_URL)
        session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with session_maker() as session:
            for device_data in devices:
                device = Device(
                    id=device_data[0],
                    device_id=device_data[1],
                    name=device_data[2],
                    device_type=device_data[3],
                    imei=device_data[4],
                    model=device_data[5],
                    android_version=device_data[6],
                    company=device_data[7],
                    status=device_data[8],
                    last_checkin=device_data[9],
                    enrollment_date=device_data[10],
                    is_active=bool(device_data[11])
                )
                session.add(device)
            
            await session.commit()
            print(f"  ✓ {len(devices)} dispositivos migrados")
        
        await engine.dispose()
    except sqlite3.OperationalError:
        print("  ✓ Tabela 'devices' não encontrada (primeira execução)")

async def migrate_policies():
    """Migra políticas do SQLite para PostgreSQL"""
    print("✓ Migrando políticas...")
    
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_id, name, type, status, camera_disabled, 
                   install_unknown_sources, factory_reset_disabled, kiosk_mode, 
                   policy_data, created_at 
            FROM policies
        """)
        policies = cursor.fetchall()
        conn.close()
        
        if not policies:
            print("  ✓ Nenhuma política para migrar")
            return
        
        engine = create_async_engine(POSTGRES_URL)
        session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with session_maker() as session:
            for policy_data in policies:
                policy = Policy(
                    id=policy_data[0],
                    device_id=policy_data[1],
                    name=policy_data[2],
                    type=policy_data[3],
                    status=policy_data[4],
                    camera_disabled=bool(policy_data[5]),
                    install_unknown_sources=bool(policy_data[6]),
                    factory_reset_disabled=bool(policy_data[7]),
                    kiosk_mode=policy_data[8],
                    policy_data=policy_data[9] or {},
                    created_at=policy_data[10]
                )
                session.add(policy)
            
            await session.commit()
            print(f"  ✓ {len(policies)} políticas migradas")
        
        await engine.dispose()
    except sqlite3.OperationalError:
        print("  ✓ Tabela 'policies' não encontrada (primeira execução)")

async def migrate_command_queue():
    """Migra fila de comandos do SQLite para PostgreSQL"""
    print("✓ Migrando fila de comandos...")
    
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_id, command, payload, status, created_at 
            FROM command_queue
        """)
        commands = cursor.fetchall()
        conn.close()
        
        if not commands:
            print("  ✓ Nenhum comando para migrar")
            return
        
        engine = create_async_engine(POSTGRES_URL)
        session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with session_maker() as session:
            for cmd_data in commands:
                command = CommandQueue(
                    id=cmd_data[0],
                    device_id=cmd_data[1],
                    command=cmd_data[2],
                    payload=cmd_data[3] or {},
                    status=cmd_data[4],
                    created_at=cmd_data[5]
                )
                session.add(command)
            
            await session.commit()
            print(f"  ✓ {len(commands)} comandos migrados")
        
        await engine.dispose()
    except sqlite3.OperationalError:
        print("  ✓ Tabela 'command_queue' não encontrada (primeira execução)")

async def migrate_telemetry():
    """Migra telemetria do SQLite para PostgreSQL"""
    print("✓ Migrando telemetria...")
    
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_id, battery_level, is_charging, free_disk_space_mb, 
                   installed_apps, latitude, longitude, foreground_app, 
                   daily_usage_stats, timestamp 
            FROM device_telemetry
        """)
        telemetry = cursor.fetchall()
        conn.close()
        
        if not telemetry:
            print("  ✓ Nenhuma telemetria para migrar")
            return
        
        engine = create_async_engine(POSTGRES_URL)
        session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with session_maker() as session:
            for tel_data in telemetry:
                telem = DeviceTelemetry(
                    id=tel_data[0],
                    device_id=tel_data[1],
                    battery_level=tel_data[2],
                    is_charging=bool(tel_data[3]) if tel_data[3] is not None else None,
                    free_disk_space_mb=tel_data[4],
                    installed_apps=tel_data[5],
                    latitude=tel_data[6],
                    longitude=tel_data[7],
                    foreground_app=tel_data[8],
                    daily_usage_stats=tel_data[9],
                    timestamp=tel_data[10]
                )
                session.add(telem)
            
            await session.commit()
            print(f"  ✓ {len(telemetry)} registros de telemetria migrados")
        
        await engine.dispose()
    except sqlite3.OperationalError:
        print("  ✓ Tabela 'device_telemetry' não encontrada (primeira execução)")

async def migrate_logs():
    """Migra logs do SQLite para PostgreSQL"""
    print("✓ Migrando logs...")
    
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_id, type, message, severity, timestamp 
            FROM logs
        """)
        logs = cursor.fetchall()
        conn.close()
        
        if not logs:
            print("  ✓ Nenhum log para migrar")
            return
        
        engine = create_async_engine(POSTGRES_URL)
        session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with session_maker() as session:
            for log_data in logs:
                log = Log(
                    id=log_data[0],
                    device_id=log_data[1],
                    type=log_data[2],
                    message=log_data[3],
                    severity=log_data[4],
                    timestamp=log_data[5]
                )
                session.add(log)
            
            await session.commit()
            print(f"  ✓ {len(logs)} logs migrados")
        
        await engine.dispose()
    except sqlite3.OperationalError:
        print("  ✓ Tabela 'logs' não encontrada (primeira execução)")

async def main():
    print("\n" + "="*60)
    print("🚀 MIGRAÇÃO SQLite → PostgreSQL - Elion MDM")
    print("="*60 + "\n")
    
    try:
        # Verificar se SQLite existe
        if not SQLITE_PATH.exists():
            print(f"⚠️  SQLite não encontrado em {SQLITE_PATH}")
            print("   Pulando migração de dados...")
        else:
            print(f"✓ SQLite encontrado: {SQLITE_PATH}\n")
        
        # Criar banco PostgreSQL
        await create_postgres_database()
        print()
        
        # Criar schema
        await init_postgres_schema()
        print()
        
        # Migrar dados (se SQLite existe)
        if SQLITE_PATH.exists():
            await migrate_users()
            await migrate_devices()
            await migrate_policies()
            await migrate_command_queue()
            await migrate_telemetry()
            await migrate_logs()
        print()
        
        print("="*60)
        print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)
        print(f"\n📖 Próximos passos:")
        print(f"  1. Verificar arquivo .env em backend/.env")
        print(f"  2. Confirmar DATABASE_URL: {POSTGRES_URL}")
        print(f"  3. Dar backup do {SQLITE_PATH}")
        print(f"  4. Executar: python -m uvicorn backend.main:app --reload\n")
        
    except Exception as e:
        print(f"\n❌ ERRO NA MIGRAÇÃO: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
