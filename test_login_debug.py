import asyncio
from backend.core.database import async_session_maker
from backend.repositories.user_repo import UserRepository
from backend.core.security import verify_password

async def test_login():
    async with async_session_maker() as db:
        credentials = {"email": "admin@empresa.com", "password": "AdminSenhaForte123!"}
        
        repo = UserRepository(db)
        user = await repo.get_by_email(credentials["email"])
        
        if not user:
            print(f"❌ Usuário não encontrado: {credentials['email']}")
            return
        
        print(f"✓ Usuário encontrado: {user.email}")
        print(f"✓ Is Admin: {user.is_admin}")  
        print(f"✓ Is Active: {user.is_active}")
        
        password_match = verify_password(credentials["password"], user.hashed_password)
        print(f"✓ Senha correta: {password_match}")

asyncio.run(test_login())
