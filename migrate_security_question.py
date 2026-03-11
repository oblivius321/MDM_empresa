"""
Script para aplicar migração de segurança ao banco PostgreSQL
Adiciona colunas security_question e security_answer_hash à tabela users
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

# Load environment variables
env_file = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_file)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não configurado. Configure em .env")


async def apply_migration():
    """Aplica a migração de segurança ao banco de dados"""
    print("=" * 70)
    print("🔒 MIGRAÇÃO: Adicionar Suporte a Pergunta de Segurança")
    print("=" * 70)
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Verificar se as colunas já existem
            print("\n📋 Verificando estrutura da tabela users...")
            
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name IN ('security_question', 'security_answer_hash')
            """))
            
            existing_columns = [row[0] for row in result.fetchall()]
            
            # Adicionar security_question se não existir
            if 'security_question' not in existing_columns:
                print("  ➕ Adicionando coluna: security_question")
                await conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN security_question VARCHAR(255)
                """))
                print("     ✅ Coluna security_question criada")
            else:
                print("  ✓ Coluna security_question já existe")
            
            # Adicionar security_answer_hash se não existir
            if 'security_answer_hash' not in existing_columns:
                print("  ➕ Adicionando coluna: security_answer_hash")
                await conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN security_answer_hash VARCHAR(255)
                """))
                print("     ✅ Coluna security_answer_hash criada")
            else:
                print("  ✓ Coluna security_answer_hash já existe")
            
            # Commit das mudanças
            await conn.commit()
            
        print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("\n📊 Nova estrutura da tabela users:")
        print("  • id (serial primary key)")
        print("  • email (unique, not null)")
        print("  • hashed_password (not null)")
        print("  • security_question (nullable) ✨ NOVO")
        print("  • security_answer_hash (nullable) ✨ NOVO")
        print("  • is_admin (boolean, default false)")
        print("  • is_active (boolean, default true)")
        
        print("\n🎯 Próximos passos:")
        print("  1. Novos usuários podem agora se registrar com pergunta de segurança")
        print("  2. Clique em 'Esqueceu a senha?' para recuperar acesso")
        print("  3. A pergunta será exibida após confirmar o email")
        print("\n" + "=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO na migração: {e}")
        return False
    finally:
        await engine.dispose()


if __name__ == "__main__":
    success = asyncio.run(apply_migration())
    exit(0 if success else 1)
