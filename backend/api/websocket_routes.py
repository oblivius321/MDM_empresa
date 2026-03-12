from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from backend.api.websockets import manager
from backend.core.security import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
from sqlalchemy.future import select
from backend.core.database import async_session_maker
from backend.models.device import Device
from backend.api.device_auth import verify_device_token
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """
    Endpoint para painéis React se conectarem para receberem eventos em tempo real.
    Lê o token JWT seguro direto do Cookie HttpOnly.
    """
    # Lê o cookie no handshake
    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise JWTError()
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect_dashboard(websocket)
    try:
        while True:
            # Mantém vivo e ouve por pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)
        logger.info("Conexão com Dashboard perdida")

@router.websocket("/ws/device/{device_id}")
async def websocket_device(websocket: WebSocket, device_id: str):
    """
    Endpoint exclusivo para cliente Android segurar uma conexão contínua com nosso servidor.
    Dessa forma injetamos Wipe/Lock direto no túnel deles sem gastar cotas do Firebase e na mesma fração de segundo.
    """
    token = websocket.headers.get("x-device-token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Validar token do device
    async with async_session_maker() as db:
        result = await db.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar_one_or_none()
        
        if not device or not device.is_active or not device.api_key_hash:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        if not verify_device_token(token, device.api_key_hash):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await manager.connect_device(websocket, device_id)
    try:
        while True:
            # Ouve mensagens que o Android mandar (ex: Ack de comandos)
            data = await websocket.receive_json()
            logger.debug(f"Via Soquete, Device {device_id} enviou: {data}")
            
            # Repassa a novidade pros painéis Front-End
            await manager.broadcast_to_dashboards({
                "type": "DEVICE_EVENT",
                "device_id": device_id,
                "payload": data
            })
            
    except WebSocketDisconnect:
        manager.disconnect_device(device_id)
        # Avisa ao painel que a bateria acabou / perdeu sinal
        await manager.broadcast_to_dashboards({
            "type": "DEVICE_DISCONNECTED",
            "device_id": device_id
        })
