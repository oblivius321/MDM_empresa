import asyncio
from sqlalchemy import text
from backend.core.database import engine

async def migrate():
    async with engine.begin() as conn:
        print("Adicionando coluna last_apps_json à tabela devices...")
        try:
            await conn.execute(text("ALTER TABLE devices ADD COLUMN last_apps_json JSONB;"))
            print("Coluna last_apps_json adicionada com sucesso.")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("Coluna last_apps_json já existe.")
            else:
                print(f"Erro ao adicionar last_apps_json: {e}")

        print("Finalizado.")

if __name__ == "__main__":
    asyncio.run(migrate())
