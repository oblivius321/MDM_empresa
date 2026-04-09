import uuid
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("mdm.api")

class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware de Produção para Observabilidade:
    - Propagação de Correlation-ID
    - Logs JSON estruturados por request
    - Tracking de latência
    """
    
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        
        start_time = time.time()
        
        # Contexto extra para o log
        device_id = request.headers.get("X-Device-ID", "unknown")
        tenant_id = request.headers.get("X-Tenant-ID", "unknown")
        
        # Dedução do event_type baseado na rota para facilitar dashboards
        event_type = "API_REQUEST"
        if "/attest" in request.url.path: event_type = "ATTESTATION"
        elif "/policy" in request.url.path: event_type = "POLICY_APPLY"
        elif "/commands" in request.url.path: event_type = "COMMAND"
        
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "correlation_id": correlation_id,
                "device_id": device_id,
                "tenant_id": tenant_id,
                "method": request.method,
                "path": request.url.path,
                "event_type": event_type
            }
        )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            response.headers["X-Correlation-ID"] = correlation_id
            
            logger.info(
                f"Request finished: {request.method} {request.url.path} - Status: {response.status_code}",
                extra={
                    "correlation_id": correlation_id,
                    "status_code": response.status_code,
                    "duration_ms": int(process_time * 1000),
                    "event_type": event_type
                }
            )
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} - Error: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "error": str(e),
                    "duration_ms": int(process_time * 1000),
                    "event_type": event_type
                }
            )
            # Reapresenta a exceção para o handler global do FastAPI
            raise e
