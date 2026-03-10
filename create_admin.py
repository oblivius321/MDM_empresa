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
            new_user = User(
                email="admin@empresa.com",
                hashed_password=get_password_hash("admin123"),
                is_admin=True
            )
            db.add(new_user)
            await db.commit()
            print("Admin criado: admin@empresa.com / admin123")
        else:
            print(f"Admin já existe no banco: {existing.email}")
            
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(seed())
