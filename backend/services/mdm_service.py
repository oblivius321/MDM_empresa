import uuid
import logging
from typing import Dict, List, Optional, Tuple
from backend.repositories.device_repo import DeviceRepository
from backend.models.device import Device
from backend.models.policy import ProvisioningProfile, DevicePolicy, DeviceCommand
from backend.services.redis_service import RedisService
from backend.core import CommandStatus

logger = logging.getLogger("mdm.service")

class MDMService:
    def __init__(self, repo: DeviceRepository, redis: RedisService = None):
        self.repo = repo
        self.redis = redis

    # ─── Provisioning Profile Management ───────────────────────────────────────

    async def create_profile(self, profile_data):
        from backend.models.policy import ProvisioningProfile, ProvisioningProfilePolicy
        # 1. Create Core Profile
        data = profile_data.model_dump(exclude={"policy_ids"})
        profile = ProvisioningProfile(**data)
        created_profile = await self.repo.create_profile(profile)
        
        # 2. Add Policy Associations
        policy_ids = getattr(profile_data, "policy_ids", [])
        if policy_ids:
            for idx, pid in enumerate(policy_ids):
                assoc = ProvisioningProfilePolicy(
                    profile_id=created_profile.id,
                    policy_id=pid,
                    priority=idx * 10 # Default spacing
                )
                self.repo.db.add(assoc)
            await self.repo.db.commit()

        return await self.repo.get_profile(created_profile.id)


    async def list_profiles(self):
        return await self.repo.list_profiles()

    async def get_profile(self, profile_id: uuid.UUID):
        return await self.repo.get_profile(profile_id)

    async def update_profile(self, profile_id: uuid.UUID, profile_data):
        from backend.models.policy import ProvisioningProfilePolicy
        from sqlalchemy import delete
        
        profile = await self.repo.get_profile(profile_id)
        if not profile:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Perfil não encontrado.")
            
        # 1. Update Basic Fields
        update_dict = profile_data.model_dump(exclude_unset=True, exclude={"policy_ids"})
        for key, value in update_dict.items():
            setattr(profile, key, value)
            
        # 2. Update Policy Associations (Full replace strategy for simplicity)
        if profile_data.policy_ids is not None:
            # Remove old
            await self.repo.db.execute(
                delete(ProvisioningProfilePolicy).where(ProvisioningProfilePolicy.profile_id == profile_id)
            )
            # Add new
            for idx, pid in enumerate(profile_data.policy_ids):
                assoc = ProvisioningProfilePolicy(
                    profile_id=profile_id,
                    policy_id=pid,
                    priority=idx * 10
                )
                self.repo.db.add(assoc)
        
        profile.version += 1
        
        # 3. Surgical Invalidation (Sênior - Avoid Sync Storms)
        await self.repo.mark_profile_devices_outdated(profile_id)
        
        await self.repo.db.commit()
        return await self.repo.get_profile(profile_id)


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

        from backend.services.policy_engine import (
            merge_policies, compute_effective_hash, compute_hash, validate_policy_structure
        )
        import time

        # 4. Upsert do Device (Atomic handshake)
        device = await self.repo.get(device_id)
        if device:
             await self.repo.update_device(device_id, {**device_data, "policy_outdated": False})
        else:
             device = Device(**device_data, policy_outdated=False)
             await self.repo.add(device)

        # ─── Pipeline de Composição de Políticas (Fase 3 Enterprise Hardened) ───
        start_time = time.perf_counter()
        
        # Camada 2: Global Policies
        global_policies = await self.repo.get_global_policies()
        
        # Camada 3: Profile Policies (Junction table)
        profile_policies = await self.repo.get_profile_policies(profile_id)
        
        # Merge de Camadas 2 e 3 (já ordenadas por priority no repo)
        all_ordered_layers = [
            {"config": p.config, "priority": p.priority, "scope": p.scope, "version": p.version}
            for p in (global_policies + profile_policies)
        ]
        
        # Camada 4: Profile Static (Fallback)
        profile_static = {
            "kiosk_enabled": profile.kiosk_enabled,
            "allowed_apps": profile.allowed_apps,
            "blocked_features": profile.blocked_features,
            "config": profile.config
        }
        
        merged_config = merge_policies(all_ordered_layers, profile_static)
        
        # ─── Senior Hardening: Validation & Size Limits ───
        validate_policy_structure(merged_config)
        
        # 6. Cálculo de Versão e Hash (Determinístico)
        max_version = max([p.version for p in (global_policies + profile_policies)] + [profile.version, 1])
        policy_hash = compute_hash(merged_config)
        effective_hash = compute_effective_hash(max_version, merged_config)

        # 7. Materialização no DevicePolicy (Concurrency Lock)
        # P2.0 Hardening: SELECT FOR UPDATE SKIP LOCKED
        existing_policy = await self.repo.get_device_policy(device_id, for_update=True)
        
        if existing_policy:
            existing_policy.profile_id = profile_id
            existing_policy.config = merged_config
            existing_policy.policy_version = max_version
            existing_policy.policy_hash = effective_hash
            # Sincroniza campos legados para compatibilidade
            existing_policy.kiosk_enabled = merged_config.get("kiosk", {}).get("enabled", profile.kiosk_enabled)
            existing_policy.allowed_apps = merged_config.get("allowed_apps", profile.allowed_apps)
            existing_policy.blocked_features = merged_config.get("restrictions", profile.blocked_features)
        else:
            new_policy = DevicePolicy(
                device_id=device_id,
                profile_id=profile_id,
                config=merged_config,
                policy_version=max_version,
                policy_hash=effective_hash,
                kiosk_enabled=merged_config.get("kiosk", {}).get("enabled", profile.kiosk_enabled),
                allowed_apps=merged_config.get("allowed_apps", profile.allowed_apps),
                blocked_features=merged_config.get("restrictions", profile.blocked_features)
            )
            self.repo.db.add(new_policy)

        # ─── Structured Telemetry (Senior Observability) ───
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info({
            "event": "policy_merge",
            "device_id": device_id,
            "policy_hash": policy_hash,
            "policy_version": max_version,
            "layers": [p.scope for p in (global_policies + profile_policies)],
            "duration_ms": duration_ms
        })

        
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
            
        commands = await self.get_pending_commands(device_id)
        
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
        Handshake de sincronização de políticas (Fase 4 - Enterprise).
        Implementa detecção de drift via Versão (Server > Device) e HASH.
        """
        from backend.models.device import Device
        device = await self.repo.get(device_id)
        policy = await self.repo.get_device_policy(device_id)
        
        if not device or not policy:
            return None
        
        # 1. Verificação de Versão Crítica (Server-side Truth)
        server_version = policy.policy_version
        server_hash = policy.policy_hash
        
        # 2. Avaliação de Drift / Outdated
        needs_sync = (
            device.policy_outdated or 
            server_version > current_version or 
            server_hash != current_hash
        )
        
        if needs_sync:
            # 3. Cache Check (Opcional - Redis)
            if self.redis:
                 cached = await self.redis.get(f"policy_cache:{server_hash}")
                 if cached: return cached

            sync_payload = {
                "version": server_version,
                "hash": server_hash,
                "config": policy.config,
                # Compatibilidade legada
                "kiosk_enabled": policy.kiosk_enabled,
                "allowed_apps": policy.allowed_apps,
                "blocked_features": policy.blocked_features,
            }

            # 4. Limpar flag outdated pós-sync
            if device.policy_outdated:
                await self.repo.update_device(device_id, {"policy_outdated": False})
                await self.repo.db.commit()

            return sync_payload
        
        return None # Device em conformidade total


    async def process_checkin(self, device_id: str, payload: dict):
        """Atualiza batimento cardíaco e telemetria profunda."""
        from datetime import datetime
        await self.repo.update_device(device_id, {"last_checkin": datetime.utcnow(), "status": "online"})
        if payload:
            await self.repo.add_telemetry(device_id, payload)

    async def enqueue_command(
        self,
        device_id: str,
        command_type: str,
        actor_id: str,
        payload: dict = None,
        user_id: int = None,
        dedupe_key: str = None,
    ) -> DeviceCommand:
        """Adiciona comando à fila segura e registra auditoria."""
        device = await self.repo.get(device_id)
        cmd = await self.repo.add_command(device_id, command_type, payload, dedupe_key=dedupe_key)

        if device and getattr(device, "external_id", None):
            await self._route_command_to_amapi(device, cmd)
        await self.repo.log_event(
            event_type="COMMAND_CREATED",
            actor_type="admin",
            actor_id=actor_id,
            user_id=user_id,
            severity="INFO",
            payload={"command_type": command_type, "device_id": device_id}
        )
        return cmd

    async def _route_command_to_amapi(self, device: Device, cmd: DeviceCommand) -> None:
        """Route command to Android Management API and save operation_id for polling.

        After successful dispatch, the command is left in DISPATCHED state.
        The background poller (amapi_operation_poller) will poll the operation
        and advance to EXECUTED or FAILED.
        """
        from fastapi import HTTPException
        from sqlalchemy.future import select
        from backend.core import CommandStatus
        from backend.models.android_management import AndroidManagementConfig
        from backend.services.android_management_service import AndroidManagementService

        result = await self.repo.db.execute(
            select(AndroidManagementConfig).where(AndroidManagementConfig.id == 1)
        )
        config = result.scalar_one_or_none()
        payload = dict(cmd.payload or {})

        if config and config.enterprise_name:
            payload["enterprise_name"] = config.enterprise_name

        try:
            response = await AndroidManagementService().send_command(
                device_external_id=device.external_id,
                command_type=cmd.command,
                payload=payload,
            )

            # Extract Google operation name for async polling
            operation_name = response.get("name")

            cmd.operation_id = operation_name
            cmd.payload = {
                **(cmd.payload or {}),
                "transport": "android_management_api",
                "amapi_response": response,
            }
            await self.repo.transition_status(cmd, CommandStatus.DISPATCHED)
            await self.repo.db.commit()

            logger.info(
                "AMAPI_COMMAND_DISPATCHED",
                extra={
                    "device_id": device.device_id,
                    "external_id": device.external_id,
                    "command_type": cmd.command,
                    "command_id": cmd.id,
                    "operation_id": operation_name,
                },
            )

        except HTTPException as exc:
            logger.error(
                "AMAPI_COMMAND_FAILED",
                extra={
                    "device_id": device.device_id,
                    "external_id": device.external_id,
                    "command_type": cmd.command,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
            cmd.error_code = f"AMAPI_{exc.status_code}"
            cmd.error_message = str(exc.detail)
            cmd.payload = {
                **(cmd.payload or {}),
                "transport": "android_management_api",
                "amapi_error": str(exc.detail),
            }
            await self.repo.transition_status(cmd, CommandStatus.FAILED, metadata={"error": str(exc.detail)})
            await self.repo.db.commit()
        except Exception as exc:
            logger.error(
                "AMAPI_COMMAND_FAILED",
                extra={
                    "device_id": device.device_id,
                    "external_id": device.external_id,
                    "command_type": cmd.command,
                    "detail": str(exc),
                },
            )
            cmd.error_code = "AMAPI_ERROR"
            cmd.error_message = str(exc)
            cmd.payload = {
                **(cmd.payload or {}),
                "transport": "android_management_api",
                "amapi_error": str(exc),
            }
            await self.repo.transition_status(cmd, CommandStatus.FAILED, metadata={"error": str(exc)})
            await self.repo.db.commit()

    async def get_device_telemetry(self, device_id: str):
        """Retorna os registros de telemetria do dispositivo."""
        return await self.repo.get_device_telemetry(device_id)

    async def get_pending_commands(self, device_id: str) -> List[DeviceCommand]:
        """Recupera comandos PENDING e os marca como DISPATCHED."""
        commands = await self.repo.get_pending_commands(device_id)
        for cmd in commands:
            if cmd.status == CommandStatus.PENDING:
                await self.repo.transition_status(
                    cmd,
                    CommandStatus.DISPATCHED,
                    metadata={"transport": "http_poll"},
                )
        if commands:
            await self.repo.db.commit()
        return commands

    async def get_command_history(self, device_id: str) -> List[DeviceCommand]:
        """Recupera o histórico completo de comandos."""
        return await self.repo.get_command_history(device_id)

    async def _legacy_ack_command_unused(self, device_id: str, command_id: int, status: str, metadata: dict = None) -> bool:
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

    async def verify_command_execution(self, device_id: str, command_id: int):
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

    async def ack_command(self, device_id: str, command_id: int, status: str, metadata: dict = None) -> bool:
        """Atualiza resultado do comando enviado pelo agente local."""
        normalized_status = self._normalize_command_status(status)
        if normalized_status not in {CommandStatus.EXECUTED, CommandStatus.FAILED, CommandStatus.ACKED}:
            return False

        cmd = await self.repo.get_command(command_id, device_id)
        if not cmd:
            return False

        if cmd.status in CommandStatus.TERMINAL_STATES:
            if cmd.status == CommandStatus.ACKED and normalized_status in {CommandStatus.EXECUTED, CommandStatus.ACKED}:
                return True
            if cmd.status == CommandStatus.FAILED and normalized_status == CommandStatus.FAILED:
                return True
            return False

        try:
            if normalized_status == CommandStatus.FAILED:
                if metadata and metadata.get("error"):
                    cmd.error_message = str(metadata["error"])
                await self.repo.transition_status(cmd, CommandStatus.FAILED, metadata)
            elif normalized_status == CommandStatus.EXECUTED:
                if cmd.status == CommandStatus.PENDING:
                    await self.repo.transition_status(
                        cmd,
                        CommandStatus.DISPATCHED,
                        metadata={"auto_dispatched": True, **(metadata or {})},
                    )
                if cmd.status == CommandStatus.DISPATCHED:
                    await self.repo.transition_status(cmd, CommandStatus.EXECUTED, metadata)
                if cmd.status == CommandStatus.EXECUTED:
                    await self.repo.transition_status(cmd, CommandStatus.ACKED, metadata)
            elif normalized_status == CommandStatus.ACKED:
                if cmd.status == CommandStatus.PENDING:
                    await self.repo.transition_status(
                        cmd,
                        CommandStatus.DISPATCHED,
                        metadata={"transport_ack": True, **(metadata or {})},
                    )
                elif cmd.status == CommandStatus.EXECUTED:
                    await self.repo.transition_status(cmd, CommandStatus.ACKED, metadata)

            await self.repo.db.commit()
        except Exception as exc:
            logger.error(f"Erro ao processar ACK do comando {command_id}: {exc}")
            await self.repo.db.rollback()
            return False

        event_map = {
            CommandStatus.ACKED: "COMMAND_ACKED",
            CommandStatus.EXECUTED: "COMMAND_EXECUTED",
            CommandStatus.FAILED: "COMMAND_FAILED",
        }
        await self.repo.log_event(
            event_type=event_map.get(cmd.status, "COMMAND_UPDATED"),
            actor_type="device",
            actor_id=device_id,
            severity="INFO" if cmd.status != CommandStatus.FAILED else "ERROR",
            payload={"command_id": str(command_id), "status": cmd.status, "metadata": metadata},
        )

        return True

    def _normalize_command_status(self, status: str) -> str:
        normalized = str(status or "").strip().upper()
        aliases = {
            "SUCCESS": CommandStatus.EXECUTED,
            "SUCCEEDED": CommandStatus.EXECUTED,
            "COMPLETED": CommandStatus.EXECUTED,
            "DONE": CommandStatus.EXECUTED,
            "ACKNOWLEDGED": CommandStatus.ACKED,
            "FAIL": CommandStatus.FAILED,
            "FAILURE": CommandStatus.FAILED,
            "ERROR": CommandStatus.FAILED,
        }
        return aliases.get(normalized, normalized)

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
            if self.redis:
                await self.redis.invalidate_verdict_cache(device_id, policy.policy_version)
            
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

    async def get_device_summary(self) -> Dict:
        return await self.repo.get_summary_stats()

    async def get_device(self, device_id: str) -> Optional[Device]:
        return await self.repo.get(device_id)

    async def _delete_amapi_device(self, device: Device) -> str:
        from fastapi import HTTPException
        from sqlalchemy.future import select
        from backend.models.android_management import AndroidManagementConfig
        from backend.services.android_management_service import AndroidManagementService

        external_id = str(getattr(device, "external_id", "") or "").strip().strip("/")
        if not external_id:
            return ""

        if external_id.startswith("enterprises/"):
            device_name = external_id
        else:
            result = await self.repo.db.execute(
                select(AndroidManagementConfig).where(AndroidManagementConfig.id == 1)
            )
            config = result.scalar_one_or_none()
            enterprise_name = str(getattr(config, "enterprise_name", "") or "").strip().strip("/")
            if not enterprise_name:
                raise HTTPException(
                    status_code=400,
                    detail="Enterprise Android Management nao conectada para excluir dispositivo AMAPI.",
                )
            if not enterprise_name.startswith("enterprises/"):
                enterprise_name = f"enterprises/{enterprise_name}"
            device_name = f"{enterprise_name}/devices/{external_id}"

        await AndroidManagementService().delete_device(device_name)
        return device_name

    async def remove_device(
        self,
        device_id: str,
        actor_id: str = "system",
        user_id: int = None,
        request = None,
    ) -> bool:
        device = await self.repo.get(device_id)
        if not device:
            return False

        amapi_device_name = ""
        if getattr(device, "external_id", None):
            amapi_device_name = await self._delete_amapi_device(device)

        device_snapshot = {
            "device_id": device.device_id,
            "name": device.name,
            "external_id": getattr(device, "external_id", None),
            "amapi_device_name": amapi_device_name or None,
        }
        removed = await self.repo.remove(device_id)
        if removed:
            await self.repo.log_event(
                event_type="DEVICE_DELETED",
                actor_type="admin" if actor_id != "system" else "system",
                actor_id=actor_id,
                user_id=user_id,
                severity="WARNING",
                device_id=device_id,
                payload=device_snapshot,
                request=request,
            )
        return removed
        
    async def list_profiles(self) -> List[ProvisioningProfile]:
        return await self.repo.list_profiles()
