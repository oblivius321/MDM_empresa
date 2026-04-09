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
