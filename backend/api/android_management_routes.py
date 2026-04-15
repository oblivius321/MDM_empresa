from datetime import datetime, timezone
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.core.database import get_db
from backend.models.android_management import (
    AndroidManagementConfig,
    AndroidManagementEnrollmentToken,
)
from backend.models.user import User
from backend.schemas.android_management import (
    AndroidManagementStatus,
    AndroidManagementDeviceResponse,
    AndroidManagementDeviceSyncResponse,
    EnrollmentTokenCreate,
    EnrollmentTokenResponse,
    SignupUrlCreate,
    SignupUrlResponse,
)
from backend.services.android_management_service import (
    AndroidManagementService,
    build_default_policy,
)


router = APIRouter(prefix="/android-management", tags=["Android Management"])
logger = logging.getLogger("mdm.android_management")


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Somente administrador pode gerenciar Android Enterprise.")
    return current_user


async def get_config(db: AsyncSession) -> AndroidManagementConfig:
    result = await db.execute(select(AndroidManagementConfig).where(AndroidManagementConfig.id == 1))
    config = result.scalar_one_or_none()
    if config:
        return config

    config = AndroidManagementConfig(id=1)
    db.add(config)
    await db.flush()
    return config


def public_base_url(request: Request) -> str:
    base_url = os.getenv("API_URL", f"{request.base_url.scheme}://{request.base_url.netloc}").rstrip("/")
    return base_url[:-4] if base_url.endswith("/api") else base_url


def default_callback_url(request: Request) -> str:
    return f"{public_base_url(request)}/api/android-management/signup-callback"


def service_or_status_error() -> AndroidManagementService:
    return AndroidManagementService()


def parse_amapi_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Invalid AMAPI device timestamp ignored", extra={"timestamp": value})
        return None

    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def amapi_device_external_id(device: dict[str, Any]) -> str:
    name = str(device.get("name") or "")
    external_id = name.rsplit("/", 1)[-1] if name else str(device.get("deviceId") or "")
    return external_id.strip()


def normalize_amapi_device_for_sync(device: dict[str, Any]) -> AndroidManagementDeviceSyncResponse:
    name = str(device.get("name") or "")
    software_info = device.get("softwareInfo") if isinstance(device.get("softwareInfo"), dict) else {}
    hardware_info = device.get("hardwareInfo") if isinstance(device.get("hardwareInfo"), dict) else {}
    non_compliance = device.get("nonComplianceDetails")

    policy_compliant = device.get("policyCompliant")
    if policy_compliant is True:
        compliance = "compliant"
    elif policy_compliant is False or non_compliance:
        compliance = "non_compliant"
    else:
        compliance = "unknown"

    external_id = amapi_device_external_id(device)
    if not external_id:
        raise HTTPException(status_code=502, detail=f"Dispositivo Google sem identificador valido: {device}")

    return AndroidManagementDeviceSyncResponse(
        external_id=external_id,
        name=name or external_id,
        model=hardware_info.get("model"),
        android_version=software_info.get("androidVersion"),
        status=str(device.get("state") or "unknown").lower(),
        last_seen=parse_amapi_datetime(device.get("lastStatusReportTime") or device.get("lastPolicySyncTime")),
        compliance=compliance,
    )


def normalize_amapi_device(device: dict[str, Any]) -> AndroidManagementDeviceResponse:
    normalized = normalize_amapi_device_for_sync(device)
    return AndroidManagementDeviceResponse(
        id=normalized.external_id,
        name=normalized.name,
        model=normalized.model,
        android_version=normalized.android_version,
        status=normalized.status,
        last_checkin=normalized.last_seen.isoformat() if normalized.last_seen else None,
        compliance=normalized.compliance,
    )


def device_mock_enabled() -> bool:
    return os.getenv("ENABLE_DEVICE_MOCK", "").strip().lower() in {"1", "true", "yes", "on"}


def build_mock_amapi_devices(enterprise_name: str) -> list[dict[str, Any]]:
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return [
        {
            "name": f"{enterprise_name}/devices/mock-device-1",
            "state": "ACTIVE",
            "policyCompliant": True,
            "lastStatusReportTime": now,
            "hardwareInfo": {"model": "Mock Android Enterprise"},
            "softwareInfo": {"androidVersion": "14"},
        }
    ]


async def ensure_device_external_id_column(db: AsyncSession) -> None:
    await db.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS external_id VARCHAR"))
    await db.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_devices_external_id_not_null
            ON devices (external_id)
            WHERE external_id IS NOT NULL
            """
        )
    )
    await db.commit()


def amapi_local_device_id(external_id: str) -> str:
    return f"amapi-{external_id}"


async def upsert_amapi_device(
    db: AsyncSession,
    device: AndroidManagementDeviceSyncResponse,
    raw_device: dict[str, Any],
) -> None:
    now = datetime.utcnow()
    db_last_seen = device.last_seen or now

    existing_result = await db.execute(
        text("SELECT device_id FROM devices WHERE external_id = :external_id"),
        {"external_id": device.external_id},
    )
    operation = "updated" if existing_result.scalar_one_or_none() else "inserted"

    metadata = {
        "source": "android_management_api",
        "amapi_name": raw_device.get("name"),
        "compliance": device.compliance,
        "synced_at": now.replace(microsecond=0).isoformat() + "Z",
    }

    await db.execute(
        text(
            """
            INSERT INTO devices (
                device_id,
                external_id,
                name,
                device_type,
                model,
                android_version,
                status,
                last_checkin,
                enrollment_date,
                is_active,
                metadata_json,
                policy_outdated
            )
            VALUES (
                :device_id,
                :external_id,
                :name,
                'android',
                :model,
                :android_version,
                :status,
                :last_checkin,
                :enrollment_date,
                TRUE,
                CAST(:metadata_json AS JSON),
                FALSE
            )
            ON CONFLICT (external_id) WHERE external_id IS NOT NULL
            DO UPDATE SET
                name = EXCLUDED.name,
                model = EXCLUDED.model,
                android_version = EXCLUDED.android_version,
                status = EXCLUDED.status,
                last_checkin = EXCLUDED.last_checkin,
                metadata_json = EXCLUDED.metadata_json
            """
        ),
        {
            "device_id": amapi_local_device_id(device.external_id),
            "external_id": device.external_id,
            "name": device.name,
            "model": device.model,
            "android_version": device.android_version,
            "status": device.status,
            "last_checkin": db_last_seen,
            "enrollment_date": now,
            "metadata_json": json.dumps(metadata, separators=(",", ":")),
        },
    )

    logger.info(
        "AMAPI_DEVICE_UPSERTED",
        extra={
            "external_id": device.external_id,
            "device_id": amapi_local_device_id(device.external_id),
            "operation": operation,
        },
    )


@router.get("/status", response_model=AndroidManagementStatus)
async def status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = await get_config(db)
    try:
        summary = service_or_status_error().config_summary()
    except HTTPException as exc:
        return AndroidManagementStatus(
            configured=False,
            signup_url_name=config.signup_url_name,
            signup_url=config.signup_url,
            enterprise_name=config.enterprise_name,
            enterprise_display_name=config.enterprise_display_name,
            policy_name=config.policy_name,
            last_error=str(exc.detail),
        )

    return AndroidManagementStatus(
        configured=True,
        project_id=summary["project_id"],
        service_account_email=summary["service_account_email"],
        service_account_file=summary["service_account_file"],
        signup_url_name=config.signup_url_name,
        signup_url=config.signup_url,
        enterprise_name=config.enterprise_name,
        enterprise_display_name=config.enterprise_display_name,
        policy_name=config.policy_name,
        last_error=config.last_error,
    )


@router.post("/signup-url", response_model=SignupUrlResponse)
async def create_signup_url(
    payload: SignupUrlCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    callback_url = payload.callback_url or default_callback_url(request)
    service = AndroidManagementService()
    config = await get_config(db)

    response = await service.create_signup_url(callback_url)
    signup_url_name = response.get("name")
    signup_url = response.get("url")
    if not signup_url_name or not signup_url:
        raise HTTPException(status_code=502, detail=f"Resposta invalida do Google: {response}")

    config.project_id = service.settings.project_id
    config.service_account_email = service.settings.client_email
    config.signup_url_name = signup_url_name
    config.signup_url = signup_url
    config.last_error = None
    await db.commit()

    return SignupUrlResponse(
        signup_url_name=signup_url_name,
        signup_url=signup_url,
        callback_url=callback_url,
    )


@router.get("/signup-callback", response_class=HTMLResponse)
async def signup_callback(
    enterpriseToken: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    service = AndroidManagementService()
    config = await get_config(db)
    if not config.signup_url_name:
        raise HTTPException(status_code=400, detail="Nenhum signupUrlName pendente no servidor.")

    try:
        enterprise = await service.create_enterprise(
            signup_url_name=config.signup_url_name,
            enterprise_token=enterpriseToken,
            display_name="Elion MDM",
        )
    except HTTPException as exc:
        config.last_error = str(exc.detail)
        await db.commit()
        raise

    config.project_id = service.settings.project_id
    config.service_account_email = service.settings.client_email
    config.enterprise_name = enterprise.get("name")
    config.enterprise_display_name = enterprise.get("enterpriseDisplayName") or "Elion MDM"
    config.last_error = None
    await db.commit()

    return HTMLResponse(
        """
        <!doctype html>
        <html lang="pt-BR">
          <head><meta charset="utf-8"><title>Android Enterprise conectado</title></head>
          <body style="font-family: Arial, sans-serif; margin: 40px;">
            <h1>Android Enterprise conectado</h1>
            <p>A enterprise foi vinculada ao Elion MDM. Volte ao painel e gere o QR oficial.</p>
          </body>
        </html>
        """
    )


@router.post("/default-policy")
async def upsert_default_policy(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = await get_config(db)
    if not config.enterprise_name:
        raise HTTPException(status_code=400, detail="Enterprise Android Management ainda nao conectada.")

    service = AndroidManagementService()
    kiosk_package = os.getenv("ANDROID_MANAGEMENT_KIOSK_PACKAGE", "").strip()
    policy = build_default_policy(kiosk_package=kiosk_package)
    response = await service.patch_policy(config.enterprise_name, "default", policy)

    config.policy_name = response.get("name") or f"{config.enterprise_name}/policies/default"
    config.last_error = None
    await db.commit()
    return response


@router.get("/devices", response_model=list[AndroidManagementDeviceResponse])
async def list_android_management_devices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = await get_config(db)
    if not config.enterprise_name:
        raise HTTPException(status_code=400, detail="Enterprise Android Management ainda nao conectada.")

    service = AndroidManagementService()
    devices = await service.list_devices(config.enterprise_name)
    normalized = [normalize_amapi_device(device) for device in devices]
    logger.info(
        "AMAPI_DEVICES_FETCHED",
        extra={
            "enterprise_name": config.enterprise_name,
            "device_count": len(normalized),
        },
    )
    return normalized


@router.get("/devices/sync", response_model=list[AndroidManagementDeviceSyncResponse])
async def sync_android_management_devices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = await get_config(db)
    if not config.enterprise_name:
        raise HTTPException(status_code=400, detail="Enterprise Android Management ainda nao conectada.")

    logger.info(
        "AMAPI_DEVICES_SYNC_STARTED",
        extra={"enterprise_name": config.enterprise_name},
    )

    await ensure_device_external_id_column(db)

    service = AndroidManagementService()
    raw_devices = await service.list_devices(config.enterprise_name)
    mock_enabled = False

    if not raw_devices and device_mock_enabled():
        mock_enabled = True
        raw_devices = build_mock_amapi_devices(config.enterprise_name)

    if not raw_devices:
        logger.info(
            "No devices found in Google enterprise",
            extra={"enterprise_name": config.enterprise_name},
        )
        logger.info(
            "AMAPI_DEVICES_SYNC_COMPLETED",
            extra={
                "enterprise_name": config.enterprise_name,
                "device_count": 0,
                "mock_enabled": mock_enabled,
            },
        )
        return []

    normalized_pairs: list[tuple[AndroidManagementDeviceSyncResponse, dict[str, Any]]] = [
        (normalize_amapi_device_for_sync(raw_device), raw_device)
        for raw_device in raw_devices
    ]

    for normalized_device, raw_device in normalized_pairs:
        await upsert_amapi_device(db, normalized_device, raw_device)

    await db.commit()

    logger.info(
        "AMAPI_DEVICES_SYNC_COMPLETED",
        extra={
            "enterprise_name": config.enterprise_name,
            "device_count": len(normalized_pairs),
            "mock_enabled": mock_enabled,
        },
    )
    return [normalized_device for normalized_device, _ in normalized_pairs]


@router.post("/enrollment-token", response_model=EnrollmentTokenResponse)
async def create_enrollment_token(
    payload: EnrollmentTokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    config = await get_config(db)
    if not config.enterprise_name:
        raise HTTPException(status_code=400, detail="Enterprise Android Management ainda nao conectada.")

    service = AndroidManagementService()
    fields_set = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
    token_payload = {}
    additional_data = {}

    if "policy_id" in fields_set and payload.policy_id:
        policy_id = payload.policy_id.strip().strip("/")
        if "/" in policy_id:
            raise HTTPException(status_code=400, detail="policy_id deve ser apenas o ID, por exemplo 'default'.")
        token_payload["policyName"] = f"{config.enterprise_name}/policies/{policy_id}"

    if "duration_minutes" in fields_set and payload.duration_minutes:
        token_payload["duration"] = f"{payload.duration_minutes * 60}s"

    if "one_time_only" in fields_set:
        token_payload["oneTimeOnly"] = payload.one_time_only

    if "additional_data" in fields_set and payload.additional_data:
        additional_data = {
            **payload.additional_data,
            "source": "elion-mdm",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        token_payload["additionalData"] = json.dumps(additional_data, separators=(",", ":"))

    response = await service.create_enrollment_token(config.enterprise_name, token_payload)
    qr_code = response.get("qrCode")
    name = response.get("name")
    if not qr_code or not name:
        raise HTTPException(status_code=502, detail=f"Resposta invalida do Google: {response}")

    token = AndroidManagementEnrollmentToken(
        name=name,
        value_prefix=(response.get("value") or "")[:8],
        policy_name=response.get("policyName") or token_payload.get("policyName"),
        qr_code=qr_code,
        additional_data=additional_data,
        expiration_timestamp=response.get("expirationTimestamp"),
        created_by=current_user.email,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)

    logger.info(
        "AMAPI_ENROLLMENT_TOKEN_GENERATED",
        extra={
            "enterprise_name": config.enterprise_name,
            "token_name": token.name,
            "created_by": current_user.email,
            "expiration": token.expiration_timestamp,
        },
    )

    return EnrollmentTokenResponse(
        id=str(token.id),
        name=token.name,
        qr_code=token.qr_code,
        expiration=token.expiration_timestamp,
        expiration_timestamp=token.expiration_timestamp,
        policy_name=token.policy_name,
    )
