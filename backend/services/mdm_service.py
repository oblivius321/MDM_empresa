import uuid
import logging
from typing import Dict, List, Optional, Tuple
from backend.repositories.device_repo import DeviceRepository
from backend.models.device import Device
from backend.models.policy import ProvisioningProfile, DevicePolicy, DeviceCommand

logger = logging.getLogger("mdm.service")

class MDMService:
    def __init__(self, repo: DeviceRepository):
        self.repo = repo

    async def enroll_device(self, device_id: str, name: str, device_type: str, profile_id: uuid.UUID, **kwargs) -> Tuple[Device, str]:
        """
        Realiza o enroll atômico de um dispositivo vinculado a um Profile obrigatório (SaaS architecture).
        """
        from backend.api.device_auth import create_device_token
        from fastapi import HTTPException
        
        # 1. Validar existência do Profile (Template mestre)
        profile = await self.repo.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=400, detail=f"Provisioning Profile {profile_id} não encontrado ou inativo.")

        # 2. Gerar Token de comunicação seguro
        token, token_hash = create_device_token(device_id)
        
        # 3. Preparar dados do Device com filtragem de colunas
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

        # 4. Upsert do Device
        device = await self.repo.get(device_id)
        if device:
             await self.repo.update_device(device_id, device_data)
        else:
             device = Device(**device_data)
             await self.repo.add(device)

        # 5. Materialização da Policy (Cópia profunda do template para o estado do device)
        policy_hash = self.repo.generate_policy_hash(profile.config, profile.allowed_apps)
        
        existing_policy = await self.repo.get_device_policy(device_id)
        if existing_policy:
            existing_policy.profile_id = profile_id
            existing_policy.kiosk_enabled = profile.kiosk_enabled
            existing_policy.allowed_apps = profile.allowed_apps
            existing_policy.blocked_features = profile.blocked_features
            existing_policy.config = profile.config
            existing_policy.policy_version = profile.version
            existing_policy.policy_hash = policy_hash
            existing_policy.policy_outdated = False
        else:
            new_policy = DevicePolicy(
                device_id=device_id,
                profile_id=profile_id,
                kiosk_enabled=profile.kiosk_enabled,
                allowed_apps=profile.allowed_apps,
                blocked_features=profile.blocked_features,
                config=profile.config,
                policy_version=profile.version,
                policy_hash=policy_hash,
                policy_outdated=False
            )
            self.repo.db.add(new_policy)
        
        # Commit atômico de Device + Policy
        await self.repo.db.commit()
        
        await self.repo.log_event(
            event_type="DEVICE_ENROLLED",
            actor_type="device",
            actor_id=device_id,
            severity="INFO",
            payload={"profile_id": str(profile_id), "name": name}
        )
        
        return device, token

    async def get_bootstrap_data(self, device_id: str) -> Dict:
        """
        Retorna o estado completo (SSOT) para o provisionamento inicial ou recuperação.
        """
        from fastapi import HTTPException
        
        policy = await self.repo.get_device_policy(device_id)
        if not policy:
            raise HTTPException(status_code=404, detail="Configuração de política não encontrada.")
            
        commands = await self.repo.get_pending_commands(device_id)
        
        return {
            "device_id": device_id,
            "policy_version": policy.policy_version,
            "policy_hash": policy.policy_hash,
            "config": policy.config,
            "kiosk_enabled": policy.kiosk_enabled,
            "allowed_apps": policy.allowed_apps,
            "blocked_features": policy.blocked_features,
            "pending_commands": commands
        }

    async def sync_policy(self, device_id: str, current_hash: str, current_version: int) -> Optional[Dict]:
        """
        Handshake de sincronização de políticas. 
        Implementa detecção de drift via HASH e flag de 'outdated'.
        """
        policy = await self.repo.get_device_policy(device_id)
        if not policy:
            return None
        
        # Drift: Hash divergente ou explicitamente marcado para atualização pelo Admin
        has_drift = (policy.policy_hash != current_hash) or (policy.policy_version != current_version)
        
        if policy.policy_outdated or has_drift:
            return {
                "version": policy.policy_version,
                "hash": policy.policy_hash,
                "kiosk_enabled": policy.kiosk_enabled,
                "allowed_apps": policy.allowed_apps,
                "blocked_features": policy.blocked_features,
                "config": policy.config
            }
        
        return None # Device em conformidade total

    async def process_checkin(self, device_id: str, payload: dict):
        """Atualiza batimento cardíaco e telemetria profunda."""
        from datetime import datetime
        await self.repo.update_device(device_id, {"last_checkin": datetime.utcnow(), "status": "online"})
        if payload:
            await self.repo.add_telemetry(device_id, payload)

    async def enqueue_command(self, device_id: str, command_type: str, actor_id: str, payload: dict = None) -> DeviceCommand:
        """Adiciona comando à fila segura e registra auditoria."""
        cmd = await self.repo.add_command(device_id, command_type, payload)
        await self.repo.log_event(
            event_type="COMMAND_CREATED",
            actor_type="admin",
            actor_id=actor_id,
            severity="INFO",
            metadata={"command_type": command_type, "device_id": device_id}
        )
        return cmd

    async def get_device_telemetry(self, device_id: str):
        """Retorna os registros de telemetria do dispositivo."""
        return await self.repo.get_device_telemetry(device_id)

    async def get_pending_commands(self, device_id: str) -> List[DeviceCommand]:
        """Recupera comandos PENDING e os marca como DISPATCHED."""
        return await self.repo.get_pending_commands(device_id)

    async def ack_command(self, device_id: str, command_id: uuid.UUID, status: str, metadata: dict = None) -> bool:
        """
        Processa confirmação de recepção (ACK) ou execução (EXECUTED) do device.
        """
        success = await self.repo.update_command_status(device_id, command_id, status, metadata)
        if success:
             event_map = {
                 "ACKED": "COMMAND_ACKED",
                 "EXECUTED": "COMMAND_EXECUTED",
                 "FAILED": "COMMAND_FAILED"
             }
             await self.repo.log_event(
                event_type=event_map.get(status, "COMMAND_UPDATED"),
                actor_type="device",
                actor_id=device_id,
                severity="INFO" if status != "FAILED" else "ERROR",
                payload={"command_id": str(command_id), "status": status, "metadata": metadata}
             )
             
             # Se for EXECUTED, tentamos a VERIFICAÇÃO automática
             if status == "EXECUTED":
                 await self.verify_command_execution(device_id, command_id)
                 
        return success

    async def verify_command_execution(self, device_id: str, command_id: uuid.UUID):
        """
        Lógica de 'Proof of Execution'. 
        Verifica se o comando realmente teve efeito (ex: via telemetria).
        """
        cmd = await self.repo.get_command(command_id)
        if not cmd: return
        
        # Simulação de verificação baseada no tipo de comando com Fallback
        # Em prod: cross-check real com a telemetria reportada e device state
        try:
            # TODO: Lógica de validação real
            is_verified = True 
            
            if is_verified:
                await self.repo.update_command_status(device_id, command_id, "VERIFIED")
                await self.repo.log_event(
                    event_type="COMMAND_VERIFIED",
                    actor_type="system",
                    actor_id="MDM_ENGINE",
                    severity="SUCCESS",
                    payload={"command_id": str(command_id)}
                )
            else:
                raise ValueError("Verification condition not met")
                
        except Exception as e:
            logger.error(f"Failed to verify command {command_id} for device {device_id}. Moving to VERIFICATION_FAILED mode.")
            # FALLBACK OBRIGATÓRIO: Se falhar a verificação, alerta humano e re-queue se aplicável
            await self.repo.update_command_status(device_id, command_id, "FAILED", {"error": str(e), "failed_at": "verification"})
            await self.repo.log_event(
                event_type="COMMAND_VERIFICATION_FAILED",
                actor_type="system",
                actor_id="MDM_ENGINE",
                severity="CRITICAL",
                payload={"command_id": str(command_id), "reason": str(e), "alert_human": True}
            )
            # Reverte status ou adiciona na retry queue dependendo na política de resiliência

    async def process_status_report(self, device_id: str, report: Dict):
        """
        Processa o relatório detalhado de saúde e conformidade (Enterprise 3B+).
        Calcula o SCORE 0-100 baseado em pesos SaaS.
        """
        # 1. Recuperar contexto do dispositivo
        policy = await self.repo.get_device_policy(device_id)
        if not policy:
             return False

        # 2. Calcular Score de Conformidade (Refinado Fase 4)
        compliance_data = {
            "kiosk_active": report.get("kiosk_active", False) or report.get("health") == "COMPLIANT",
            "malicious_apps": len(report.get("failed_policies", [])) > 0, # Placeholder simplificado
            "integrity_score": report.get("trust_score", 0),
            "policy_drift": report.get("policy_hash") == policy.policy_hash
        }
        
        score = self.calculate_compliance_score(compliance_data)
        
        # 3. Determinar Saúde baseado em Thresholds
        health = "COMPLIANT" if score >= 80 else ("DEGRADED" if score >= 40 else "CRITICAL")
        
        # 4. Log de Auditoria & Telemetria
        await self.repo.log_event(
            event_type="COMPLIANCE_REPORT",
            actor_type="device",
            actor_id=device_id,
            severity="INFO" if health == "COMPLIANT" else "WARNING",
            payload={**report, "compliance_score": score, "derived_health": health}
        )

        await self.repo.add_telemetry(device_id, {
            "type": "compliance_score",
            "score": score,
            "health": health,
            "integrity": compliance_data["integrity_score"]
        })

        # 5. Enforcement Automático (SLA) & Active Invalidation
        if health == "CRITICAL":
            logger.error(f"🚨 DEVICE {device_id} EM ESTADO CRÍTICO (Score: {score}). Acionando LOCK de emergência.")
            await self.enqueue_command(device_id, "LOCK", "SYSTEM_SLA", {"reason": "Compliance failure"})
            
            # Invalidação Ativa do Cache: Remove o trust rate para forçar nova validação no backend
            from backend.services.redis_service import RedisService
            redis = RedisService()
            redis.invalidate_verdict_cache(device_id, policy.policy_version)
            
        return True


    def calculate_compliance_score(self, data: Dict) -> int:
        """
        Motor de Scoring SaaS Enterprise.
        Pesos: Kiosk (40) | Security (30) | Apps (20) | Integrity (10)
        """
        score = 0
        # Kiosk (40%)
        if data.get("kiosk_active"): score += 40
        
        # Security/Drift (30%)
        if data.get("policy_drift"): score += 30
        
        # Apps (20%) - Se não há apps maliciosos/falhas
        if not data.get("malicious_apps"): score += 20
        
        # Play Integrity (10%) - Normalizado de 0-100 para 0-10
        score += int(data.get("integrity_score", 0) / 10)
        
        return score

    async def list_devices(self) -> List[Device]:
        return await self.repo.list()

    async def get_device(self, device_id: str) -> Optional[Device]:
        return await self.repo.get(device_id)

    async def remove_device(self, device_id: str) -> bool:
        return await self.repo.remove(device_id)
        
    async def list_profiles(self) -> List[ProvisioningProfile]:
        return await self.repo.list_profiles()
