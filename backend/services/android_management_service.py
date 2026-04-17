from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import HTTPException
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account
from jose import jwt


AMAPI_BASE_URL = "https://androidmanagement.googleapis.com/v1"
AMAPI_SCOPE = "https://www.googleapis.com/auth/androidmanagement"
JWT_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
logger = logging.getLogger("mdm.android_management")


AMAPI_COMMAND_MAP = {
    "lock": "LOCK",
    "lock_screen": "LOCK",
    "lock_device": "LOCK",
    "reboot": "REBOOT",
    "reboot_device": "REBOOT",
    "wipe": "WIPE",
    "wipe_device": "WIPE",
}

AMAPI_KIOSK_COMMANDS = {
    "kiosk",
    "enable_kiosk",
    "disable_kiosk",
    "update_kiosk",
}


def _extract_google_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("error_description")
            status = error.get("status")
            if message and status:
                return f"{message} ({status})"
            if message:
                return str(message)
            if error.get("error"):
                return str(error["error"])

        message = payload.get("message") or payload.get("error_description") or payload.get("error")
        if message:
            return str(message)

    text = response.text.strip()
    if text:
        return text[:1000]
    return "Google retornou erro sem corpo de resposta."


@dataclass
class AndroidManagementSettings:
    project_id: str
    service_account_file: Path
    client_email: str
    private_key: str
    token_uri: str


class AndroidManagementService:
    _cached_token: Optional[str] = None
    _cached_token_expiry: Optional[datetime] = None

    def __init__(self) -> None:
        self.settings = self._load_settings()

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parent.parent.parent

    def _load_settings(self) -> AndroidManagementSettings:
        key_file = os.getenv("ANDROID_MANAGEMENT_SERVICE_ACCOUNT_FILE", "").strip()
        if not key_file:
            raise HTTPException(
                status_code=500,
                detail="ANDROID_MANAGEMENT_SERVICE_ACCOUNT_FILE nao configurado.",
            )

        key_path = Path(key_file)
        if not key_path.is_absolute():
            key_path = self._repo_root() / key_path

        if not key_path.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Arquivo da service account nao encontrado: {key_path}",
            )

        try:
            data = json.loads(key_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Falha ao ler service account JSON: {exc}",
            ) from exc

        project_id = os.getenv("ANDROID_MANAGEMENT_PROJECT_ID") or data.get("project_id")
        client_email = data.get("client_email")
        private_key = data.get("private_key")
        token_uri = data.get("token_uri", "https://oauth2.googleapis.com/token")

        if not project_id or not client_email or not private_key:
            raise HTTPException(
                status_code=500,
                detail="Service account JSON incompleto para Android Management API.",
            )

        return AndroidManagementSettings(
            project_id=project_id,
            service_account_file=key_path,
            client_email=client_email,
            private_key=private_key,
            token_uri=token_uri,
        )

    def config_summary(self) -> dict[str, Any]:
        return {
            "project_id": self.settings.project_id,
            "service_account_email": self.settings.client_email,
            "service_account_file": str(self.settings.service_account_file),
            "configured": True,
        }

    async def _access_token(self) -> str:
        now = datetime.utcnow()
        if (
            self._cached_token
            and self._cached_token_expiry
            and self._cached_token_expiry > now + timedelta(seconds=60)
        ):
            return self._cached_token

        issued_at = int(now.timestamp())
        expires_at = issued_at + 3600
        assertion = jwt.encode(
            {
                "iss": self.settings.client_email,
                "scope": AMAPI_SCOPE,
                "aud": self.settings.token_uri,
                "iat": issued_at,
                "exp": expires_at,
            },
            self.settings.private_key,
            algorithm="RS256",
        )

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.settings.token_uri,
                data={
                    "grant_type": JWT_GRANT_TYPE,
                    "assertion": assertion,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if response.status_code >= 400:
            message = _extract_google_error_message(response)
            raise HTTPException(
                status_code=502,
                detail=f"Falha ao obter token Google OAuth ({response.status_code}): {message}",
            )

        payload = response.json()
        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not token:
            raise HTTPException(status_code=502, detail="OAuth Google nao retornou access_token.")

        self._cached_token = token
        self._cached_token_expiry = now + timedelta(seconds=expires_in)
        return token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        allow_not_found: bool = False,
    ) -> dict[str, Any]:
        url = f"{AMAPI_BASE_URL}/{path.lstrip('/')}"

        def send_request():
            credentials = service_account.Credentials.from_service_account_file(
                str(self.settings.service_account_file),
                scopes=[AMAPI_SCOPE],
            )
            session = AuthorizedSession(credentials)
            request_kwargs = {
                "params": params,
                "headers": {"Content-Type": "application/json"},
                "timeout": 45,
            }
            if body is not None:
                request_kwargs["json"] = body

            return session.request(method, url, **request_kwargs)

        response = await asyncio.to_thread(send_request)

        if response.status_code >= 400:
            if allow_not_found and response.status_code == 404:
                return {"not_found": True}

            error_data = {}
            try:
                error_data = response.json()
            except Exception:
                pass
            
            # Tenta extrair a mensagem de erro legível do Google
            error_msg = error_data.get("error", {}).get("message") or response.text
            raise HTTPException(
                status_code=502,
                detail=f"Google API Error ({response.status_code}): {error_msg}"
            )

        if not response.content:
            return {}
        return response.json()

    async def create_signup_url(self, callback_url: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "signupUrls",
            params={
                "projectId": self.settings.project_id,
                "callbackUrl": callback_url,
            },
        )

    async def create_enterprise(
        self,
        *,
        signup_url_name: str,
        enterprise_token: str,
        display_name: str = "Elion MDM",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "enterprises",
            params={
                "projectId": self.settings.project_id,
                "signupUrlName": signup_url_name,
                "enterpriseToken": enterprise_token,
            },
            body={"enterpriseDisplayName": display_name},
        )

    async def patch_policy(
        self,
        enterprise_name: str,
        policy_id: str,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"{enterprise_name}/policies/{policy_id}",
            body=policy,
        )

    async def create_enrollment_token(
        self,
        enterprise_name: str,
        token: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"{enterprise_name}/enrollmentTokens",
            body=token,
        )

    async def list_devices(self, enterprise_name: str) -> list[dict[str, Any]]:
        response = await self._request("GET", f"{enterprise_name}/devices")
        devices = response.get("devices", [])
        return devices if isinstance(devices, list) else []

    async def delete_device(self, device_name: str) -> dict[str, Any]:
        clean_device_name = str(device_name or "").strip().strip("/")
        if not clean_device_name:
            raise HTTPException(status_code=400, detail="device_name obrigatorio para exclusao AMAPI.")
        if not clean_device_name.startswith("enterprises/") or "/devices/" not in clean_device_name:
            raise HTTPException(
                status_code=400,
                detail="device_name AMAPI deve estar no formato enterprises/{enterprise}/devices/{device}.",
            )

        response = await self._request("DELETE", clean_device_name, allow_not_found=True)
        logger.info(
            "AMAPI_DEVICE_DELETED",
            extra={"device_name": clean_device_name, "not_found": bool(response.get("not_found"))},
        )
        return response

    async def get_operation(self, operation_name: str) -> dict[str, Any]:
        """Poll a Google long-running operation by its full resource name.

        The operation_name is the full path returned by issueCommand,
        e.g. 'enterprises/.../devices/.../operations/123'.
        Returns the operation object with 'done', 'response', and/or 'error' fields.
        """
        return await self._request("GET", operation_name)

    def _enterprise_name_from_payload(self, payload: dict[str, Any]) -> str:
        enterprise_name = str(
            payload.get("enterprise_name")
            or payload.get("enterprise")
            or os.getenv("ANDROID_MANAGEMENT_ENTERPRISE_NAME", "")
        ).strip().strip("/")

        if not enterprise_name:
            raise HTTPException(
                status_code=500,
                detail="Enterprise Android Management nao informada para envio de comando.",
            )

        if not enterprise_name.startswith("enterprises/"):
            enterprise_name = f"enterprises/{enterprise_name}"
        return enterprise_name

    def _device_name(self, enterprise_name: str, device_external_id: str) -> str:
        clean_external_id = str(device_external_id or "").strip().strip("/")
        if not clean_external_id:
            raise HTTPException(status_code=400, detail="device_external_id obrigatorio para comando AMAPI.")

        if clean_external_id.startswith("enterprises/"):
            return clean_external_id
        return f"{enterprise_name}/devices/{clean_external_id}"

    def _log_command_failed(
        self,
        *,
        device_name: str,
        command_type: str,
        detail: Any,
        status_code: Optional[int] = None,
    ) -> None:
        extra = {
            "device_name": device_name,
            "command_type": command_type,
            "detail": detail,
        }
        if status_code is not None:
            extra["status_code"] = status_code
        logger.error("AMAPI_COMMAND_FAILED", extra=extra)

    async def send_command(
        self,
        device_external_id: str,
        command_type: str,
        payload: dict,
    ) -> dict[str, Any]:
        payload = payload or {}
        device_name = str(device_external_id or "")
        normalized_command = str(command_type or "").strip().lower()

        try:
            enterprise_name = self._enterprise_name_from_payload(payload)
            device_name = self._device_name(enterprise_name, device_external_id)

            if normalized_command in AMAPI_KIOSK_COMMANDS:
                policy_id = str(payload.get("policy_id") or "default").strip().strip("/")
                policy = payload.get("policy")
                if not isinstance(policy, dict):
                    raise HTTPException(
                        status_code=400,
                        detail="Comando kiosk via AMAPI exige payload.policy com a policy Android Management.",
                    )

                response = await self.patch_policy(enterprise_name, policy_id, policy)
                logger.info(
                    "AMAPI_COMMAND_SENT",
                    extra={
                        "device_name": device_name,
                        "command_type": command_type,
                        "amapi_action": "POLICY_UPDATE",
                        "policy_id": policy_id,
                    },
                )
                return response

            amapi_command = AMAPI_COMMAND_MAP.get(normalized_command)
            if not amapi_command:
                raise HTTPException(
                    status_code=400,
                    detail=f"Comando nao mapeado para AMAPI: {command_type}",
                )

            response = await self._request(
                "POST",
                f"{device_name}:issueCommand",
                body={"type": amapi_command},
            )
            logger.info(
                "AMAPI_COMMAND_SENT",
                extra={
                    "device_name": device_name,
                    "command_type": command_type,
                    "amapi_command": amapi_command,
                    "command_name": response.get("name"),
                },
            )
            return response
        except HTTPException as exc:
            self._log_command_failed(
                device_name=device_name,
                command_type=command_type,
                status_code=exc.status_code,
                detail=exc.detail,
            )
            raise
        except Exception as exc:
            self._log_command_failed(
                device_name=device_name,
                command_type=command_type,
                detail=str(exc),
            )
            raise


def build_default_policy(kiosk_package: str = "") -> dict[str, Any]:
    policy: dict[str, Any] = {
        "factoryResetDisabled": True,
        "installUnknownSourcesAllowed": False,
        "debuggingFeaturesAllowed": False,
        "mountPhysicalMediaDisabled": True,
        "modifyAccountsDisabled": True,
        "usbFileTransferDisabled": True,
        "networkEscapeHatchEnabled": True,
        "ensureVerifyAppsEnabled": True,
        "defaultPermissionPolicy": "GRANT",
        "playStoreMode": "WHITELIST",
        "systemUpdate": {"type": "AUTOMATIC"},
        "statusReportingSettings": {
            "applicationReportsEnabled": True,
            "deviceSettingsEnabled": True,
            "softwareInfoEnabled": True,
            "memoryInfoEnabled": True,
            "networkInfoEnabled": True,
            "displayInfoEnabled": True,
            "powerManagementEventsEnabled": True,
            "hardwareStatusEnabled": True,
            "systemPropertiesEnabled": True,
        },
        "shortSupportMessage": {
            "defaultMessage": "Dispositivo gerenciado pela Elion MDM."
        },
        "longSupportMessage": {
            "defaultMessage": "Entre em contato com o administrador de TI da empresa."
        },
    }

    if kiosk_package:
        policy["applications"] = [
            {
                "packageName": kiosk_package,
                "installType": "KIOSK",
                "defaultPermissionPolicy": "GRANT",
            }
        ]
        policy["kioskCustomization"] = {
            "systemNavigation": "NAVIGATION_DISABLED",
            "statusBar": "NOTIFICATIONS_AND_SYSTEM_INFO_DISABLED",
            "powerButtonActions": "POWER_BUTTON_AVAILABLE",
            "systemErrorWarnings": "ERROR_AND_WARNINGS_MUTED",
        }

    return policy
