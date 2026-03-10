import json
from typing import Dict, List, Any
from fastapi import WebSocket, WebSocketDisconnect
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Armazena as conexões WebSocket ativas divididas por 'roles'
        # 'dashboard' -> Lista de administradores React conectados
        # 'device' -> Dicionário de conexões ativas de dispositivos Android (deviceID -> WebSocket)
        self.active_dashboards: List[WebSocket] = []
        self.active_devices: Dict[str, WebSocket] = {}

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.active_dashboards.append(websocket)
        logger.info(f"Dashboard conectado. Total de admins logados: {len(self.active_dashboards)}")

    async def connect_device(self, websocket: WebSocket, device_id: str):
        await websocket.accept()
        self.active_devices[device_id] = websocket
        logger.info(f"Dispositivo Android conectado: {device_id}. Total de celulaes vivos na malha: {len(self.active_devices)}")
        # Avisa aos dashboards que um dispositivo entrou
        await self.broadcast_to_dashboards({
            "type": "DEVICE_CONNECTED",
            "device_id": device_id,
        })

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.active_dashboards:
            self.active_dashboards.remove(websocket)
            logger.info("Dashboard desconectado.")

    def disconnect_device(self, device_id: str):
        if device_id in self.active_devices:
            del self.active_devices[device_id]
            logger.info(f"Dispositivo Android desconectado da malha: {device_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_command_to_device(self, device_id: str, command_data: Dict[str, Any]) -> bool:
        """
        Dispara instantaneamente um comando JSON massivo ao celudar alvo (Android) caso esteja atrelado à malha.
        Retorna True se entregue no fio HTTP Upgrade.
        """
        if device_id in self.active_devices:
            ws = self.active_devices[device_id]
            try:
                await ws.send_json(command_data)
                logger.info(f"Comando {command_data.get('command')} injetado via WebSockets no Android: {device_id}")
                return True
            except Exception as e:
                logger.error(f"Erro ao empurrar TCP pelo socket do Dispositivo {device_id}: {e}")
                self.disconnect_device(device_id)
        return False

    async def broadcast_to_dashboards(self, message: Dict[str, Any]):
        """
        Espalha a fofoca para todas as telas React do Centro de Comando do Mundo 
        avisando que uma política/comando/ping aconteceu em um Android.
        """
        dead_connections = []
        for connection in self.active_dashboards:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        
        # Ceifa as conexões React zumbis do pool ram python
        for dead in dead_connections:
            self.disconnect_dashboard(dead)

# Padrão Singleton. Importe este `manager` nas rotas FastAPI.
manager = ConnectionManager()
