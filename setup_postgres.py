"""
Script de Setup do PostgreSQL - Windows Local
Valida conexão, cria banco e tabelas, e popula dados iniciais
"""
import asyncio
import os
import sys
from pathlib import Path

# Adicionen o diretório raiz ao path
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

# Carregar variáveis de ambiente
env_file = root_dir / ".env"
load_dotenv(dotenv_path=env_file)

# Configurações
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "mdm_project")
DB_HOST = "localhost"  # Windows local
DB_PORT = 5432

# URLs
POSTGRES_ADMIN_URL = f"postgresql+asyncpg://postgres:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
POSTGRES_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


async def test_postgres_connection():
    """Testa conexão com PostgreSQL"""
    print("🔍 Testando conexão com PostgreSQL...")
    try:
        # Conectar ao banco 'postgres' padrão para verificar
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database="postgres"
        )
        await conn.close()
        print(f"✅ Conexão bem-sucedida! PostgreSQL rodando em {DB_HOST}:{DB_PORT}")
        return True
    except Exception as e:
        print(f"❌ ERRO de Conexão: {e}")
        print(f"\n⚠️  Verifique:")
        print(f"   - PostgreSQL está rodando em {DB_HOST}:{DB_PORT}?")
        print(f"   - Usuário '{DB_USER}' e senha estão corretos?")
        print(f"   - Firewall não está bloqueando a porta 5432?")
        return False


async def create_database():
    """Cria o banco de dados se não existir"""
    print("\n📦 Verificando/Criando banco de dados...")
    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database="postgres"
        )
        
        # Verificar se banco existe
        exists = await conn.fetchval(
            f"SELECT 1 FROM pg_database WHERE datname = $1", DB_NAME
        )
        
        if not exists:
            await conn.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"✅ Banco de dados '{DB_NAME}' criado com sucesso")
        else:
            print(f"✅ Banco de dados '{DB_NAME}' já existe")
        
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Erro ao criar banco: {e}")
        return False


async def create_tables():
    """Cria as tabelas no banco de dados"""
    print("\n🏗️  Criando estrutura de tabelas...")
    
    from backend.core.database import Base, engine
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Tabelas criadas/verificadas com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        return False


async def create_admin_user():
    """Cria usuário admin padrão"""
    print("\n👤 Verificando usuário admin...")
    
    from backend.models.user import User
    from backend.core.security import get_password_hash
    from backend.core.database import async_session_maker
    
    try:
        async with async_session_maker() as session:
            # Verificar se admin já existe
            result = await session.execute(
                text("SELECT id FROM users WHERE email = 'admin@elion.mdm' LIMIT 1")
            )
            admin_exists = result.fetchone() is not None
            
            if not admin_exists:
                # Criar admin
                admin = User(
                    email="admin@elion.mdm",
                    hashed_password=get_password_hash("Admin@1234"),
                    is_admin=True,
                    is_active=True
                )
                session.add(admin)
                await session.commit()
                print("✅ Usuário admin criado com sucesso")
                print(f"   📧 Email: admin@elion.mdm")
                print(f"   🔑 Senha: Admin@1234")
                print(f"   ⚠️  ALTERE A SENHA IMEDIATAMENTE após o primeiro login!")
            else:
                print("✅ Usuário admin já existe")
            
            return True
    except Exception as e:
        print(f"❌ Erro ao criar admin: {e}")
        return False


async def main():
    """Executa o setup completo"""
    print("=" * 60)
    print("🚀 SETUP DO POSTGRESQL - WINDOWS LOCAL")
    print("=" * 60)
    print(f"Host: {DB_HOST}")
    print(f"Porta: {DB_PORT}")
    print(f"Usuário: {DB_USER}")
    print(f"Banco: {DB_NAME}")
    print("=" * 60)
    
    # Step 1: Test connection
    if not await test_postgres_connection():
        print("\n❌ Não foi possível conectar ao PostgreSQL. Aborting.")
        return False
    
    # Step 2: Create database
    if not await create_database():
        print("\n❌ Erro ao criar banco. Aborting.")
        return False
    
    # Step 3: Create tables
    if not await create_tables():
        print("\n❌ Erro ao criar tabelas. Aborting.")
        return False
    
    # Step 4: Create admin user
    if not await create_admin_user():
        print("\n⚠️  Admin pode não ter sido criado, mas tabelas estão prontas")
    
    print("\n" + "=" * 60)
    print("✅ SETUP CONCLUÍDO COM SUCESSO!")
    print("=" * 60)
    print("\n🎯 Próximos passos:")
    print("   1. Verifique se a variável DATABASE_URL no .env aponta para localhost:")
    print("      DATABASE_URL=postgresql+asyncpg://postgres:Sherlock314@localhost:5432/mdm_project")
    print("   2. Rode a API: uvicorn backend.main:app --reload")
    print("   3. Acesse: http://localhost:8000/docs")
    print("\n")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
