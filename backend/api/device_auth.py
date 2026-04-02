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
    token: Optional[str] = Query(None), # Para websockets (fallback seguro)
) -> Device:
    # 🛡️ Padrão Enterprise: Headers estritamente separados
    # Device NÃO deve usar o header 'Authorization' (reservado para Admin/JWT)
    device_token = x_device_token or token
    
    if not device_token:
        # Rejeitar se o device tentar usar Authorization em vez de X-Device-Token
        if request.headers.get("Authorization"):
            raise HTTPException(
                status_code=401, 
                detail="Invalid auth context. Devices must use X-Device-Token."
            )
        raise HTTPException(status_code=401, detail="Device token missing")
        
    try:
        # Formato esperado: "device_id:secret"
        parts = device_token.split(":", 1)
        if len(parts) != 2:
            raise ValueError()
        token_device_id = parts[0]
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid device token format")
        
    # Obtém a sessão do banco
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        result = await db.execute(select(Device).where(Device.device_id == token_device_id))
        device = result.scalar_one_or_none()
        
        if not device:
            raise HTTPException(status_code=401, detail="Device not registered")
            
        # Validação de Hash (API Key)
        if not device.api_key_hash or not verify_device_token(device_token, device.api_key_hash):
            raise HTTPException(status_code=401, detail="Invalid device credentials")
            
        if not device.is_active:
            raise HTTPException(status_code=403, detail="Device is deactivated")
            
        # 🛡️ SEGURANÇA (Padrão Enterprise): Validação de Escopo (Path vs Token)
        # Impede que Device A acesse recursos do Device B usando seu próprio token
        path_device_id = request.path_params.get("device_id")
        if path_device_id and path_device_id != device.device_id:
             import logging
             logger = logging.getLogger("security")
             logger.warning(
                 f"🔥 [Security Alert] Cross-device access attempt! "
                 f"Token_Device: {device.device_id}, Path_Device: {path_device_id}"
             )
             raise HTTPException(
                 status_code=403, 
                 detail="Access denied: Resource belongs to another device."
             )
            
        return device
    finally:
        await db.close()
