from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.api.websockets import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """
    Endpoint para painéis React se conectarem para receberem eventos em tempo real
    """
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
