"""
Script para adicionar pergunta de segurança a usuários existentes
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from backend.core.security import get_password_hash

# Load environment
env_file = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_file)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não configurado")


async def add_security_question():
    """Adiciona pergunta de segurança a um usuário existente"""
    
    engine = create_async_engine(DATABASE_URL)
    
    print("=" * 70)
    print("🔒 ADICIONAR PERGUNTA DE SEGURANÇA A USUÁRIO EXISTENTE")
    print("=" * 70)
    
    try:
        # Receber dados do usuário
        email = input("\n📧 Email do usuário: ").strip()
        if not email:
            print("❌ Email obrigatório")
            return
        
        question = input("❓ Pergunta de segurança: ").strip()
        if not question or len(question) < 5:
            print("❌ Pergunta obrigatória (mínimo 5 caracteres)")
            return
        
        answer = input("✍️  Resposta: ").strip()
        if not answer or len(answer) < 2:
            print("❌ Resposta obrigatória (mínimo 2 caracteres)")
            return
        
        # Normalizar resposta
        answer_normalized = answer.lower().strip()
        answer_hash = get_password_hash(answer_normalized)
        
        async with engine.begin() as conn:
            # Verificar se usuário existe
            result = await conn.execute(
                text("SELECT id, email FROM users WHERE email = :email"),
                {"email": email}
            )
            user = result.fetchone()
            
            if not user:
                print(f"❌ Usuário '{email}' não encontrado")
                return
            
            user_id = user[0]
            
            # Atualizar usuário
            await conn.execute(
                text("""
                    UPDATE users 
                    SET security_question = :question,
                        security_answer_hash = :answer_hash
                    WHERE id = :id
                """),
                {
                    "id": user_id,
                    "question": question,
                    "answer_hash": answer_hash
                }
            )
            
            await conn.commit()
            
            print("\n✅ PÉRGUNTA DE SEGURANÇA ADICIONADA!")
            print(f"   📧 Email: {email}")
            print(f"   ❓ Pergunta: {question}")
            print(f"   ✓ Resposta hashificada com segurança")
            print("\n🎯 Agora você pode usar 'Esqueceu minha senha'")
            print("=" * 70)
        
    except Exception as e:
        print(f"❌ Erro: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(add_security_question())
