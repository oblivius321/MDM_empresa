import asyncio
from backend.core.database import get_db
from backend.models.user import User
from backend.core.security import get_password_hash
from sqlalchemy import select

async def seed():
    try:
        db_gen = get_db()
        db = await anext(db_gen)
        
        result = await db.execute(select(User).where(User.email == "admin@empresa.com"))
        existing = result.scalars().first()
        
        if not existing:
            import os
            default_password = os.getenv("DEFAULT_ADMIN_PASSWORD")
            
            if not default_password or len(default_password) < 12:
                print("❌ ERRO CRÍTICO: Variável DEFAULT_ADMIN_PASSWORD não configurada no .env ou é inferior a 12 caracteres.")
                print("Por segurança, o Admin padrão não foi criado automaticamente com senha fraca.")
                print("Utilize: python backend/create_admin.py --email seu@email.com --password SenhaForte123!")
                return
                
            new_user = User(
                email="admin@empresa.com",
                hashed_password=get_password_hash(default_password),
                is_admin=True
            )
            db.add(new_user)
            await db.commit()
            print(f"✅ Admin criado: admin@empresa.com com senha dos secrets.")
        else:
            print(f"Admin já existe no banco: {existing.email}")
            
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(seed())
