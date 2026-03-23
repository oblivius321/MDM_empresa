#!/usr/bin/env python3
"""
Script para executar migrações SQL no banco de dados.
Uso: python backend/run_migration.py <migration_file> [--db-url=<url>]
Exemplo: python backend/run_migration.py migrations/003_create_rbac_tables.sql
         python backend/run_migration.py migrations/003_create_rbac_tables.sql --db-url=postgresql+asyncpg://postgres:Sherlock314@localhost:5432/mdm_project
"""

import asyncio
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def run_migration(migration_file: str, db_url: str = None) -> None:
    """Executa um arquivo de migração SQL."""
    
    # Se não fornecido, usar do config
    if not db_url:
        from backend.core.config import DATABASE_URL
        db_url = DATABASE_URL
    
    # Validar que o arquivo existe
    migration_path = Path(migration_file)
    if not migration_path.exists():
        print(f"❌ Erro: Arquivo de migração não encontrado: {migration_file}")
        sys.exit(1)
    
    # Ler o arquivo SQL
    with open(migration_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Criar engine e executar
    engine = create_async_engine(db_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            print(f"📝 Executando migração: {migration_file}")
            print(f"🗄️  Conectando a: {db_url.split('@')[1] if '@' in db_url else 'database'}")
            
            # Dividir por ponto-e-vírgula e executar cada comando
            commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip()]
            
            for i, command in enumerate(commands, 1):
                try:
                    await conn.execute(text(command))
                    print(f"  ✅ Comando {i}/{len(commands)} executado")
                except Exception as e:
                    error_msg = str(e)
                    # Ignorar erros de CREATE IF NOT EXISTS
                    if "already exists" in error_msg or "duplicate key" in error_msg:
                        print(f"  ⚠️  Comando {i}/{len(commands)}: {error_msg} (ignorado)")
                    else:
                        print(f"  ❌ Comando {i}/{len(commands)}: {error_msg}")
                        # Não parar - continuar com próximos comandos
            
            print(f"✅ Migração concluída!")
    
    except Exception as e:
        print(f"❌ Erro ao executar migração: {e}")
        sys.exit(1)
    
    finally:
        await engine.dispose()


async def main():
    if len(sys.argv) < 2:
        print("Uso: python backend/run_migration.py <migration_file> [--db-url=<url>]")
        print("Exemplo: python backend/run_migration.py migrations/003_create_rbac_tables.sql")
        print("         python backend/run_migration.py migrations/003_create_rbac_tables.sql --db-url=postgresql+asyncpg://postgres:password@localhost:5432/mdm_project")
        sys.exit(1)
    
    migration_file = sys.argv[1]
    db_url = None
    
    # Procurar por --db-url=
    for arg in sys.argv[2:]:
        if arg.startswith("--db-url="):
            db_url = arg.split("=", 1)[1]
            break
    
    await run_migration(migration_file, db_url)


if __name__ == "__main__":
    asyncio.run(main())
