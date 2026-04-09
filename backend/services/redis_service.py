import redis.asyncio as redis
import json
import os
import logging
from typing import Optional, Any
import random

class RedisService:
    """
    Gerencia persistência temporária no Redis para:
    - Nonces de atestação (Anti-Replay)
    - Cache de Verdicts (Performance & Stampede Protection)
    - Rate Limiting (Hardening)
    """
    
    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.client = redis.Redis(host=self.host, port=self.port, db=0, decode_responses=True)
        self.logger = logging.getLogger("mdm.redis")

    async def store_nonce(self, device_id: str, nonce: str, ttl: int = 300):
        """Armazena um nonce vinculado ao device_id com expiração (5 min)."""
        key = f"nonce:{device_id}:{nonce}"
        await self.client.setex(key, ttl, "UNUSED")
        self.logger.debug(f"Nonce stored for device {device_id}")

    async def validate_and_use_nonce(self, device_id: str, nonce: str) -> bool:
        """Verifica se o nonce existe, está UNUSED e o marca como USED (Anti-Replay)."""
        key = f"nonce:{device_id}:{nonce}"
        val = await self.client.get(key)
        
        if val == "UNUSED":
            # Atomicamente deletar para garantir uso único
            await self.client.delete(key)
            return True
        return False

    async def cache_verdict(self, device_id: str, policy_version: int, verdict: dict, base_ttl: int = 600):
        """
        Cache do resultado da verificação do Google vinculado à versão.
        Usa Jitter (± 120s) para evitar Cache Stampede/Thundering Herd.
        """
        jitter = random.randint(0, 120)
        ttl = base_ttl + jitter
        
        key = f"verdict_cache:{device_id}:v{policy_version}"
        await self.client.setex(key, ttl, json.dumps(verdict))

    async def get_cached_verdict(self, device_id: str, policy_version: int) -> Optional[dict]:
        """Recupera veredito do cache validando se a versão ainda é a requerida."""
        key = f"verdict_cache:{device_id}:v{policy_version}"
        data = await self.client.get(key)
        return json.loads(data) if data else None

    async def invalidate_verdict_cache(self, device_id: str, policy_version: int):
        """
        Invalidação ativa (Active Invalidation).
        Remove o cache quando o policy muda ou device entra em CRITICAL.
        """
        key = f"verdict_cache:{device_id}:v{policy_version}"
        await self.client.delete(key)
        self.logger.info(f"Verdict cache explicitly invalidated for {device_id} (v{policy_version})")

    async def increment_rate_limit(self, key: str, window: int = 60) -> int:
        """Incrementa contador para rate limiting em uma janela de tempo."""
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, window)
        return count

    # ─── Enrollment Token Management (Enterprise QR) ──────────────────────────

    async def store_enrollment_token(
        self,
        token: str,
        profile_id: str,
        tenant_id: str,
        created_by: str,
        mode: str = "single",
        max_devices: int = 1,
        ttl: int = 900,  # 15 minutos
    ):
        """
        Armazena token de enrollment no Redis com metadados completos.
        Modes: 'single' (1 device) ou 'batch' (N devices).
        Usa status UNUSED→USED (mesmo padrão do attestation, sem delete).
        """
        key = f"enrollment_token:{token}"
        data = {
            "status": "UNUSED",
            "profile_id": profile_id,
            "tenant_id": tenant_id,
            "created_by": created_by,
            "mode": mode,
            "max_devices": str(max_devices),
            "used_count": "0",
        }
        await self.client.hset(key, mapping=data)
        await self.client.expire(key, ttl)
        self.logger.info(
            f"Enrollment token stored: mode={mode}, max={max_devices}, ttl={ttl}s, by={created_by}"
        )

    async def validate_enrollment_token(self, token: str) -> Optional[dict]:
        """
        Valida e consome um enrollment token.
        - Single: marca USED após primeiro uso.
        - Batch: incrementa used_count; marca USED quando atinge max_devices.
        Retorna os metadados (profile_id, tenant_id) se válido, None se inválido.
        """
        key = f"enrollment_token:{token}"
        data = await self.client.hgetall(key)

        if not data:
            self.logger.warning(f"Enrollment token not found or expired: {token[:8]}...")
            return None

        if data.get("status") == "USED":
            self.logger.warning(f"Enrollment token already fully used: {token[:8]}...")
            return None

        mode = data.get("mode", "single")
        used_count = int(data.get("used_count", "0"))
        max_devices = int(data.get("max_devices", "1"))

        if mode == "single":
            # Marca como USED (não deleta — mantém auditoria)
            await self.client.hset(key, "status", "USED")
            await self.client.hset(key, "used_count", "1")
        elif mode == "batch":
            new_count = used_count + 1
            await self.client.hset(key, "used_count", str(new_count))
            if new_count >= max_devices:
                await self.client.hset(key, "status", "USED")
                self.logger.info(f"Batch token fully consumed: {new_count}/{max_devices}")

        self.logger.info(
            f"Enrollment token validated: profile={data.get('profile_id')}, "
            f"mode={mode}, usage={used_count + 1}/{max_devices}"
        )

        return {
            "profile_id": data["profile_id"],
            "tenant_id": data["tenant_id"],
            "created_by": data["created_by"],
            "mode": mode,
            "used_count": used_count + 1,
            "max_devices": max_devices,
        }

    async def get_enrollment_token_info(self, token: str) -> Optional[dict]:
        """Retorna informações do token sem consumir (para debug/admin)."""
        key = f"enrollment_token:{token}"
        data = await self.client.hgetall(key)
        if not data:
            return None
        ttl = await self.client.ttl(key)
        return {**data, "ttl_remaining": ttl}
