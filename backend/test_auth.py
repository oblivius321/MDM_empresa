import pytest
from httpx import AsyncClient, ASGITransport
import backend.models.telemetry
import backend.models.policy
import backend.models.user
import backend.models.device
from backend.main import app
from backend.api.device_auth import create_device_token, verify_device_token

@pytest.mark.asyncio
async def test_create_device_token():
    device_id = "test-device-id"
    token, token_hash = create_device_token(device_id)
    
    # Token must include device_id
    assert token.startswith(f"{device_id}:")
    
    # Validation
    assert verify_device_token(token, token_hash)
    assert not verify_device_token("invalid", token_hash)
    assert not verify_device_token(token, "invalid_hash")

@pytest.mark.asyncio
async def test_protected_device_route():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Tentar acessar sem token
        response = await ac.post("/api/devices/test-sec-device-1/checkin", json={})
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_websocket_requires_token():
    from fastapi.testclient import TestClient
    from fastapi.websockets import WebSocketDisconnect
    
    client = TestClient(app)
    # Tentar conectar websockets sem token (deveria dar 403 Forbidden do FastAPI Test Client ao invés de HTTP code)
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/api/ws/dashboard"):
            pass
    assert e.value.code == 1008
    
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/api/ws/device/some-device"):
            pass
    assert e.value.code == 1008
