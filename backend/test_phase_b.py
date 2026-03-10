import pytest
from httpx import AsyncClient, ASGITransport
import backend.models.telemetry
import backend.models.policy
import backend.models.user
import backend.models.device
from backend.main import app
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.models.user import User
from backend.core.security import get_password_hash
import uuid

# Helper to create a test user
async def create_test_user():
    db_gen = get_db()
    db = await anext(db_gen)
    test_email = f"test_{uuid.uuid4().hex}@test.com"
    test_password = "password123"
    
    # Injeta um usuário de teste no banco para tentar o login
    try:
        new_user = User(
            email=test_email,
            hashed_password=get_password_hash(test_password),
            is_admin=True
        )
        db.add(new_user)
        await db.commit()
    finally:
        await db.close()
        
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
