import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.core.security import get_password_hash
import uuid

# Helper to create a test user
async def create_test_user():
    from backend.core.database import engine, Base
    
    # Create tables if not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create test user
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        test_email = f"test_{uuid.uuid4().hex}@test.com"
        test_password = "password123"
        
        new_user = User(
            email=test_email,
            hashed_password=get_password_hash(test_password),
            is_admin=True
        )
        session.add(new_user)
        await session.commit()
        
    return test_email, test_password

@pytest.mark.asyncio
async def test_login_returns_cookie():
    email, password = await create_test_user()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        
        assert response.status_code == 200
        assert "message" in response.json()
        assert "user" in response.json()
        
        # Verify the cookie
        cookies = response.cookies
        assert "access_token" in cookies

@pytest.mark.asyncio
async def test_rate_limiter_blocks_abuse():
    email, password = await create_test_user()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # slowapi usa o IP do ASGI scope (geralmente fake no testclient), vamos disparar 6 requests seguidos
        for _ in range(5):
            res = await ac.post("/api/auth/login", json={"email": "wrong@test.com", "password": "123"})
            assert res.status_code == 401
            
        # O sexto deve ser bloqueado por rate limit (limite é 5 por minuto)
        res_blocked = await ac.post("/api/auth/login", json={"email": "wrong@test.com", "password": "123"})
        assert res_blocked.status_code == 429
