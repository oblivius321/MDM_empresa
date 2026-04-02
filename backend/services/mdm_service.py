from typing import Dict, List, Optional, Tuple
from backend.repositories.device_repo import DeviceRepository
from backend.models.device import Device
from backend.models.policy import Policy


class MDMService:
    def __init__(self, repo: DeviceRepository):
        self.repo = repo

    async def process_checkin(self, device_id: str, payload: dict):
        from datetime import datetime
        await self.repo.update_device(device_id, {"last_checkin": datetime.utcnow(), "status": "online"})
        if payload:
            await self.repo.add_telemetry(device_id, payload)


    async def enroll_device(self, device_id: str, name: str, device_type: str, **kwargs) -> Tuple[Device, str]:
        """
        Realiza o enroll (registro ou atualização) de um dispositivo.
        Filtra kwargs para evitar erros de colunas inexistentes no SQLAlchemy.
        """
        from backend.api.device_auth import create_device_token
        token, token_hash = create_device_token(device_id)
        
        # 1. Separar campos conhecidos dos campos extras (metadata)
        # Lista de colunas reais no modelo Device
        valid_columns = {
            "name", "device_type", "imei", "model", 
            "android_version", "company", "status", "is_active"
        }
        
        device_data = {
            "device_id": device_id,
            "name": name,
            "device_type": device_type,
            "status": "online",
            "is_active": True,
            "api_key_hash": token_hash
        }
        
        metadata = {}
        for k, v in kwargs.items():
            if k in valid_columns:
                device_data[k] = v
            else:
                metadata[k] = v
        
        device_data["metadata_json"] = metadata
        
        # 2. Tentar recuperar o dispositivo existente
        device = await self.repo.get(device_id)
        
        if device:
            # ✅ RE-ENROLLMENT: Se o bootstrap_secret passou, permitimos atualizar o token
            # Isso resolve o erro 500 caso o admin queira reinserir um device
            updated = await self.repo.update_device(device_id, device_data)
            if not updated:
                from fastapi import HTTPException
                raise HTTPException(status_code=500, detail="Falha crítica ao atualizar dispositivo existente")
            return updated, token
        
        # 3. NOVO DEVICE
        new_device = Device(**device_data)
        added = await self.repo.add(new_device)
        return added, token

    async def update_device(self, device_id: str, updates: Dict) -> Optional[Device]:
        return await self.repo.update_device(device_id, updates)

    async def remove_device(self, device_id: str) -> bool:
        return await self.repo.remove(device_id)

    async def apply_policy(self, device_id: str, policy_data: Dict) -> bool:
        # Criando poliTICA
        policy = await self.repo.add_policy(device_id, policy_data)
        if policy:
             # Queue a command so device pulls the new policy
             await self.repo.add_command(device_id, "apply_policy", payload=policy_data)
             return True
        return False

    async def wipe_device(self, device_id: str) -> bool:
        device = await self.repo.get(device_id)
        if not device:
             return False
        await self.repo.add_command(device_id, "wipe_device")
        await self.repo.update_device(device_id, {"status": "locked"})
        return True

    async def get_pending_commands(self, device_id: str):
        return await self.repo.get_pending_commands(device_id)

    async def list_devices(self) -> List[Device]:
        return await self.repo.list()

    async def get_device(self, device_id: str) -> Optional[Device]:
        return await self.repo.get(device_id)

    async def list_policies(self) -> List[Policy]:
        return await self.repo.list_policies()
