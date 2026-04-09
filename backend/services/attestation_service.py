import hashlib
import hmac
import os
import time
import base64
import json
import logging
import uuid
from typing import Dict, Optional, Tuple
from .redis_service import RedisService

class AttestationService:
    """
    Motor de Atestação Enterprise (Fase 4).
    Garante que o dispositivo é confiável via Play Integrity API + Anti-Replay.
    """
    
    def __init__(self, redis: RedisService):
        self.redis = redis
        self.secret_key = os.getenv("ATTESTATION_SECRET", "elion_master_secret_2026")
        self.logger = logging.getLogger("mdm.attestation")

    async def generate_nonce(self, device_id: str, tenant_id: str) -> str:
        """
        Gera um nonce assinado e vinculado (Binding).
        Payload: device_id | tenant_id | request_id | expires_at
        """
        request_id = str(uuid.uuid4())
        issued_at = int(time.time())
        expires_at = issued_at + 300 # 5 min TTL
        
        payload = f"{device_id}:{tenant_id}:{request_id}:{expires_at}"
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        nonce = base64.urlsafe_b64encode(f"{payload}.{signature}".encode()).decode().strip("=")
        
        # Armazena no Redis com status UNUSED (Anti-Replay) using tenant_id e request_id
        # Key schema: nonce:{tenant_id}:{request_id}
        await self.redis.client.setex(f"nonce:{tenant_id}:{request_id}", 300, json.dumps({
            "device_id": device_id,
            "tenant_id": tenant_id,
            "nonce": nonce,
            "status": "UNUSED"
        }))
        
        return nonce

    async def verify_device_integrity(self, device_id: str, tenant_id: str, token: str, nonce: str) -> Dict:
        """
        Valida o token de integridade e calcula o Trust Score.
        Executa: Sig Validation -> Anti-Replay -> Binding Check.
        """
        try:
            # 1. Decode & Signature Validation (Local)
            decoded = base64.urlsafe_b64decode(nonce + "=" * (4 - len(nonce) % 4)).decode()
            payload, signature = decoded.split(".")
            
            expected_sig = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected_sig):
                raise ValueError("INVALID_NONCE_SIGNATURE")
            
            p_device_id, p_tenant_id, request_id, expires_at = payload.split(":")
            
            # 2. Expiration & Binding Check (com Clock Skew tolerado ±60s)
            current_time = int(time.time())
            if current_time > (int(expires_at) + 60):
                raise ValueError("NONCE_EXPIRED")
            if p_device_id != device_id or p_tenant_id != tenant_id:
                raise ValueError("NONCE_BINDING_MISMATCH")

            # 3. Anti-Replay (Redis Multi-Tenant Check)
            nonce_key = f"nonce:{tenant_id}:{request_id}"
            nonce_data_json = await self.redis.client.get(nonce_key)
            if not nonce_data_json:
                raise ValueError("NONCE_NOT_FOUND")
                
            nonce_data = json.loads(nonce_data_json)
            if nonce_data["status"] == "USED":
                raise ValueError("NONCE_ALREADY_USED_REPLAY_ATTACK")
            if nonce_data["nonce"] != nonce:
                raise ValueError("NONCE_TAMPERED")

            # Mark as USED without deleting to avoid race conditions (TTL is kept)
            nonce_data["status"] = "USED"
            ttl_left = await self.redis.client.ttl(nonce_key)
            if ttl_left > 0:
                await self.redis.client.setex(nonce_key, ttl_left, json.dumps(nonce_data))

        except Exception as e:
            self.logger.error(f"Attestation Blocked: {str(e)} for device {device_id}")
            return {"trust_score": 0, "status": "COMPROMISED", "reason": str(e)}

        # 4. Cache Check (Performance) vinculado à versão da engine
        cached = await self.redis.get_cached_verdict(device_id, policy_version=1) # Baseline version
        if cached:
            self.logger.info(f"Using cached verdict for {device_id}")
            return cached

        # 5. Google API Verification (Mocked logic for structure)
        # Em produção: usar googleapiclient.discovery.build('playintegrity', 'v1')
        verdict = await self._call_google_play_api(token)
        
        # 6. Scoring Calculation (Pesos Ponderados)
        trust_score = self._calculate_trust_score(verdict)
        
        result = {
            "trust_score": trust_score,
            "status": "TRUSTED" if trust_score >= 80 else ("UNTRUSTED" if trust_score >= 40 else "COMPROMISED"),
            "verdicts": verdict,
            "timestamp": time.time()
        }

        # 7. Cache Result (10 min)
        await self.redis.cache_verdict(device_id, policy_version=1, verdict=result)
        return result

    def _calculate_trust_score(self, verdict: Dict) -> int:
        """
        Calcula Score 0-100.
        Pesos:
        - MEETS_STRONG_INTEGRITY: 100
        - MEETS_DEVICE_INTEGRITY: 60
        - MEETS_BASIC_INTEGRITY: 20
        """
        device_integrity = verdict.get("deviceIntegrity", {}).get("deviceRecognitionVerdict", [])
        
        if "MEETS_STRONG_INTEGRITY" in device_integrity:
            return 100
        if "MEETS_DEVICE_INTEGRITY" in device_integrity:
            return 60
        if "MEETS_BASIC_INTEGRITY" in device_integrity:
            return 20
        return 0

    async def _call_google_play_api(self, token: str) -> Dict:
        """
        Placeholder para chamada real ao Google Play Developer API.
        """
        # Aqui iria o client.decodeIntegrityToken(packageName, {'integrityToken': token})
        # Mocking a successful response for implementation structure:
        return {
            "deviceIntegrity": {"deviceRecognitionVerdict": ["MEETS_DEVICE_INTEGRITY"]},
            "appIntegrity": {"appRecognitionVerdict": "PLAY_RECOGNIZED"},
            "accountDetails": {"appLicensingVerdict": "LICENSED"}
        }
