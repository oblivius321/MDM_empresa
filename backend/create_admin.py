#!/usr/bin/env python3
"""
Script para criar o usuário admin inicial com RBAC.
Usa as variáveis de ambiente DEFAULT_ADMIN_PASSWORD, EMAIL, etc.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os
from backend.core.config import DATABASE_URL
from backend.core.security import get_password_hash
from backend.models.user import User
from backend.models.role import Role, RoleEnum
from backend.models.permission import Permission
from backend.core.database import Base


async def create_admin():
    """Cria usuário admin e roles padrão no banco."""
    
    # Obter senha padrão do admin
    default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "AdminSenhaForte123!")
    
    # Criar engine e session factory
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # 1. Criar tabelas se não existirem
            print("📝 Criando tabelas...")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print("✅ Tabelas criadas/verificadas")
            
            # 2. Criar roles padrão
            print("\n🔐 Criando roles padrão...")
            roles_data = [
                {
                    "name": "SUPER_ADMIN",
                    "role_type": RoleEnum.SUPER_ADMIN,
                    "description": "Acesso total ao sistema",
                    "priority": 1000,
                    "is_system_role": True,
                },
                {
                    "name": "ADMIN",
                    "role_type": RoleEnum.ADMIN,
                    "description": "Administrador com restrições",
                    "priority": 100,
                    "is_system_role": True,
                },
                {
                    "name": "OPERATOR",
                    "role_type": RoleEnum.OPERATOR,
                    "description": "Operador de dispositivos",
                    "priority": 10,
                    "is_system_role": True,
                },
                {
                    "name": "VIEWER",
                    "role_type": RoleEnum.VIEWER,
                    "description": "Visualizador (somente leitura)",
                    "priority": 1,
                    "is_system_role": True,
                },
            ]
            
            roles_created = []
            for role_data in roles_data:
                # Verificar se role já existe
                stmt = select(Role).filter_by(name=role_data["name"])
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    print(f"  ⚠️  Role {role_data['name']} já existe, pulando...")
                    roles_created.append(existing)
                else:
                    role = Role(**role_data)
                    session.add(role)
                    print(f"  ✅ Role {role_data['name']} criado")
                    roles_created.append(role)
            
            await session.flush()  # Flush para obter IDs
            
            # 3. Criar usuário admin
            print("\n👤 Criando usuário admin...")
            admin_email = "admin@empresa.com"
            
            # Verificar se admin já existe
            stmt = select(User).filter_by(email=admin_email)
            result = await session.execute(stmt)
            existing_admin = result.scalar_one_or_none()
            
            if existing_admin:
                print(f"  ⚠️  Admin {admin_email} já existe!")
                
                # Se existir mas não tiver SUPER_ADMIN, atribuir
                admin_user = existing_admin
                super_admin_role = next((r for r in roles_created if r.name == "SUPER_ADMIN"), None)
                
                if super_admin_role and super_admin_role not in admin_user.roles:
                    admin_user.roles.append(super_admin_role)
                    print(f"  ✅ Role SUPER_ADMIN atribuído ao admin")
            else:
                # Criar novo admin
                hashed_password = get_password_hash(default_admin_password)
                admin_user = User(
                    email=admin_email,
                    hashed_password=hashed_password,
                    is_admin=True,  # Legacy field
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                
                # Atribuir role SUPER_ADMIN
                super_admin_role = next((r for r in roles_created if r.name == "SUPER_ADMIN"), None)
                if super_admin_role:
                    admin_user.roles.append(super_admin_role)
                
                session.add(admin_user)
                print(f"  ✅ Admin {admin_email} criado com senha: {default_admin_password}")
            
            # 4. Commit
            await session.commit()
            print("\n✅ Banco inicializado com sucesso!")
            print(f"\n📧 Email: {admin_email}")
            print(f"🔑 Senha: {default_admin_password}")
            print("\nVocê pode fazer login agora!")
    
    except Exception as e:
        print(f"\n❌ Erro ao criar admin: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        await engine.dispose()


async def main():
    """Função principal."""
    print("=" * 60)
    print("🚀 Inicializador do MDM - Criando Admin & Roles")
    print("=" * 60)
    print(f"📍 Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'N/A'}")
    print()
    
    await create_admin()


if __name__ == "__main__":
    asyncio.run(main())
