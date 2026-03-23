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
        from backend.api.device_auth import create_device_token
        token, token_hash = create_device_token(device_id)
        
        device = await self.repo.get(device_id)
        if device:
            # ✅ SEGURANÇA (P1.2): Impedir takeover de devices já cadastrados.
            # Se já existe, admin precisa deletar explicitamente no painel antes de permitir novo enroll.
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Este dispositivo já está registrado. Para reinseri-lo, remova-o primeiro pelo painel de controle."
            )
            if updated_device:
                return updated_device, token
            return device, token # Fallback
        
        # NOVO DEVICE
        new_device = Device(device_id=device_id, name=name, device_type=device_type, is_active=True, status="online", api_key_hash=token_hash, **kwargs)
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
