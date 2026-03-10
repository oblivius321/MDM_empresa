import secrets
import hashlib
from fastapi import HTTPException, Security, Request, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, Tuple
from backend.core.database import get_db
from backend.models.device import Device

def create_device_token(device_id: str) -> Tuple[str, str]:
    """Gera um token limpo e o seu hash SHA-256 para salvar no banco."""
    raw_secret = secrets.token_urlsafe(32)
    token = f"{device_id}:{raw_secret}"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash

def verify_device_token(token: str, stored_hash: str) -> bool:
    if not token or not stored_hash:
        return False
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return secrets.compare_digest(token_hash, stored_hash)

async def get_current_device(
    request: Request,
    x_device_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None), # Para websockets
) -> Device:
    # Priorizar header, fallback para query (útil para websockets)
    device_token = x_device_token or token
    
    if not device_token:
        raise HTTPException(status_code=401, detail="Device token missing")
        
    try:
        device_id, _ = device_token.split(":", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid device token format")
        
    # Obtém a sessão do banco
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        result = await db.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar_one_or_none()
        
        if not device:
            raise HTTPException(status_code=401, detail="Device not found")
            
        if not device.api_key_hash or not verify_device_token(device_token, device.api_key_hash):
            raise HTTPException(status_code=401, detail="Invalid device token")
            
        if not device.is_active:
            raise HTTPException(status_code=403, detail="Device is inactive")
            
        # Verificar se a rota atual acessa o mesmo device_id (autorização)
        path_device_id = request.path_params.get("device_id")
        if path_device_id and path_device_id != device.device_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this device's resources")
            
        return device
    finally:
        await db.close()
