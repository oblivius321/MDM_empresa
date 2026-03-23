"""
Decorators para proteção de endpoints baseado em permissões.

Uso:
    @app.get("/api/devices/wipe")
    @require_permission("devices:wipe")
    async def wipe_device(device_id: str, current_user: User = Depends(get_current_user)):
        ...
"""

from functools import wraps
from fastapi import HTTPException, status, Depends
from fastapi.requests import Request
from backend.models.user import User
from typing import List, Callable, Optional


def require_permission(*permissions: str):
    """
    Decorator para verificar se o usuário tem uma permissão específica.
    
    Suporta múltiplas permissões:
    - Se 1 permissão: user DEVE ter essa
    - Se N permissões: user PODE ter qualquer uma (OR)
    
    Uso:
        @require_permission("devices:wipe")
        async def wipe(...):
            pass
        
        @require_permission("users:create", "users:update")  # user pode ter qualquer uma
        async def manage_user(...):
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extrair user do contexto de functools
            # Em FastAPI, o user é passado como dependency
            current_user: User = kwargs.get("current_user")
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Não autenticado"
                )
            
            if not current_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Usuário inativo"
                )
            
            # Verificar se tem QUALQUER uma das permissões
            if not current_user.has_any_permission(*permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permissão necessária: {', '.join(permissions)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_all_permissions(*permissions: str):
    """
    Decorator para verificar se o usuário tem TODAS as permissões.
    
    Uso:
        @require_all_permissions("devices:read", "devices:lock")
        async def lock_device(...):
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: User = kwargs.get("current_user")
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Não autenticado"
                )
            
            if not current_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Usuário inativo"
                )
            
            # Verificar se tem TODAS as permissões
            if not current_user.has_all_permissions(*permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permissões necessárias: {', '.join(permissions)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(*role_types: str):
    """
    Decorator para verificar se o usuário tem um role específico.
    
    Uso:
        @require_role("SUPER_ADMIN")
        async def delete_logs(...):
            pass
        
        @require_role("ADMIN", "SUPER_ADMIN")  # Pode ter qualquer um
        async def manage_users(...):
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: User = kwargs.get("current_user")
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Não autenticado"
                )
            
            if not current_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Usuário inativo"
                )
            
            # Verificar role type
            user_roles = {role.role_type.value for role in current_user.roles}
            if not any(role_name in user_roles for role_name in role_types):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role necessário: {', '.join(role_types)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_mfa_verified(func: Callable):
    """
    Decorator para exigir que o usuário tenha MFA verificado.
    
    IMPORTANTE: Implementação real depende de sistema de MFA.
    Por agora, é um placeholder.
    
    Uso:
        @require_mfa_verified
        @require_permission("devices:wipe")
        async def wipe_device(...):
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        current_user: User = kwargs.get("current_user")
        request: Request = kwargs.get("request")
        
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Não autenticado"
            )
        
        # TODO: Implementar verificação real de MFA
        # Por agora, apenas verificar se token MFA está no request
        mfa_token = request.headers.get("X-MFA-Token") if request else None
        
        if not mfa_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA verification required for this action"
            )
        
        # TODO: Validar token MFA
        
        return await func(*args, **kwargs)
    
    return wrapper


# ============================================================================
# DECORATORS PARA AUDITORIA
# ============================================================================

def audit_action(action_name: str, resource_type: str):
    """
    Decorator para logar automaticamente uma ação critica.
    
    Uso:
        @audit_action("DEVICE_WIPE", "devices")
        @require_permission("devices:wipe")
        async def wipe_device(device_id: str):
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # A implementação real de auditoria será no endpoint
            # Este decorator é principalmente para documentação/segurança
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# HELPER: Extractor de current_user em decorators
# ============================================================================

class PermissionChecker:
    """Helper class para verificar permissões dentro de endpoints."""
    
    def __init__(self, current_user: User):
        self.current_user = current_user
    
    def has_permission(self, permission: str) -> bool:
        """Verifica se user tem uma permissão."""
        return self.current_user.has_permission(permission)
    
    def has_any_permission(self, *permissions: str) -> bool:
        """Verifica se user tem qualquer uma das permissões."""
        return self.current_user.has_any_permission(*permissions)
    
    def has_all_permissions(self, *permissions: str) -> bool:
        """Verifica se user tem todas as permissões."""
        return self.current_user.has_all_permissions(*permissions)
    
    def has_role(self, role_type: str) -> bool:
        """Verifica se user tem um role específico."""
        return any(
            role.role_type.value == role_type
            for role in self.current_user.roles
        )
    
    def assert_permission(self, permission: str):
        """Levanta exceção se não tiver permissão."""
        if not self.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
    
    def assert_any_permission(self, *permissions: str):
        """Levanta exceção se não tiver qualquer uma das permissões."""
        if not self.has_any_permission(*permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these permissions required: {', '.join(permissions)}"
            )
    
    def assert_role(self, role_type: str):
        """Levanta exceção se não tiver o role."""
        if not self.has_role(role_type):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role_type}"
            )
