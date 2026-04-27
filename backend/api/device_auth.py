import secrets
import hashlib
from fastapi import HTTPException, Security, Request, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, Tuple
from backend.core.database import get_db
from backend.models.device import Device

def create_device_token(device_id: str) -> Tuple[str, str]:
    """Gera um token opaco e o seu hash SHA-256 para salvar no banco."""
    token = secrets.token_urlsafe(48)
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
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> Device:
    # Log de depuração profunda
    import logging
    auth_logger = logging.getLogger("mdm.auth")
    
    # Capturar todos os headers para entender o que o Android está mandando
    headers_dict = dict(request.headers)
    auth_logger.info(f"🔍 [AUTH DEBUG] Headers recebidos: {headers_dict}")
    auth_logger.info(f"🔍 [AUTH DEBUG] x_device_token: {x_device_token} | auth_header: {authorization} | query_token: {token}")

    # 🛡️ Padrão Enterprise: Tenta X-Device-Token, depois Authorization (Bearer), depois Query
    device_token = x_device_token
    
    if not device_token and authorization:
        if authorization.lower().startswith("bearer "):
            device_token = authorization[7:]
        else:
            device_token = authorization # Tenta usar o valor puro se não tiver Bearer
        
    if not device_token:
        device_token = token
    
    if not device_token:
        auth_logger.warning(f"❌ [AUTH] Token ausente. Host: {request.client.host if request.client else 'unknown'}")
        raise HTTPException(status_code=401, detail="Device token missing")
        
    # O token agora é opaco (V4 Mitigation).
    # Calculamos o hash em memória e buscamos direto pela coluna `api_key_hash`.
    token_hash = hashlib.sha256(device_token.encode()).hexdigest()
        
    # Obtém a sessão do banco
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Lookup seguro via hash da API key
        result = await db.execute(select(Device).where(Device.api_key_hash == token_hash))
        device = result.scalar_one_or_none()
        
        if not device or not device.api_key_hash:
            raise HTTPException(status_code=401, detail="Invalid device credentials")
            
        # Verificação constante de tempo (timing attack prevention)
        if not verify_device_token(device_token, device.api_key_hash):
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
