import asyncio
import argparse
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import async_session_maker, engine, Base
from backend.models.user import User
from backend.repositories.user_repo import UserRepository
from backend.core.security import get_password_hash

async def create_first_admin(email: str, password: str):
    async with engine.begin() as conn:
        print("Criando tabelas ou verificando banco de dados...")
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session_maker() as db:
        repo = UserRepository(db)
        
        # Verifica se já tem esse admin
        existing_admin = await repo.get_by_email(email)
        if existing_admin:
            print(f"O administrador '{email}' já está criado e configurado no banco de dados!")
            return

        print(f"Registrando o primeiro CEO/Admin corporativo: {email}...")
        
        hashed_password = get_password_hash(password)
        admin = User(
            email=email,
            hashed_password=hashed_password,
            is_admin=True,
            is_active=True
        )
        await repo.create(admin)
        print(f"SUCESSO: Administrador '{email}' criado com as senhas criptografadas bcrypt no Banco SQLite.")
        print("Agora você já pode autorizar novos analistas pelo Frontend usando essas credenciais!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Povoar o banco com o Admin da Elion")
    parser.add_argument("--email", type=str, default="admin@empresa.com", help="Email do Admin Elite")
    parser.add_argument("--password", type=str, default="admin123", help="Senha secreta do Admin Elite")
    args = parser.parse_args()

    asyncio.run(create_first_admin(args.email, args.password))
