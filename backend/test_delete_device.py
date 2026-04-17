from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.models.android_management
import backend.models.audit_log
import backend.models.device
import backend.models.permission
import backend.models.policy
import backend.models.role
import backend.models.telemetry
import backend.models.user
from backend.api import routes
from backend.core.database import Base
from backend.main import app
from backend.models.android_management import AndroidManagementConfig
from backend.models.device import Device
from backend.models.policy import DeviceCommand, DevicePolicy, PolicyState, ProvisioningProfile
from backend.models.telemetry import DeviceTelemetry
from backend.repositories.device_repo import DeviceRepository
from backend.services.android_management_service import AndroidManagementService
from backend.services.mdm_service import MDMService


class FakeDeleteService:
    def __init__(self, removed: bool = True):
        self.removed = removed
        self.calls = []

    async def remove_device(self, device_id: str, **kwargs) -> bool:
        self.calls.append((device_id, kwargs))
        return self.removed


def override_user(is_admin: bool):
    return SimpleNamespace(
        id=1,
        email="admin@example.com" if is_admin else "user@example.com",
        is_admin=is_admin,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_delete_device_endpoint_requires_admin():
    fake_service = FakeDeleteService()
    app.dependency_overrides[routes.get_current_user] = lambda: override_user(False)
    app.dependency_overrides[routes.get_service] = lambda: fake_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/devices/device-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert fake_service.calls == []


@pytest.mark.asyncio
async def test_delete_device_endpoint_returns_no_content():
    fake_service = FakeDeleteService()
    app.dependency_overrides[routes.get_current_user] = lambda: override_user(True)
    app.dependency_overrides[routes.get_service] = lambda: fake_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete("/api/devices/device-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""
    assert fake_service.calls[0][0] == "device-1"
    assert fake_service.calls[0][1]["actor_id"] == "admin@example.com"


@pytest_asyncio.fixture
async def sqlite_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session

    await engine.dispose()


async def table_count(session: AsyncSession, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def legacy_policy_count(session: AsyncSession) -> int:
    return await session.scalar(text("SELECT COUNT(*) FROM policies"))


@pytest.mark.asyncio
async def test_remove_device_deletes_amapi_and_local_related_rows(sqlite_session, monkeypatch):
    deleted_devices = []

    async def fake_delete_device(self, device_name: str):
        deleted_devices.append(device_name)
        return {}

    monkeypatch.setattr(AndroidManagementService, "delete_device", fake_delete_device)

    await sqlite_session.execute(
        text(
            """
            CREATE TABLE policies (
                id INTEGER PRIMARY KEY,
                device_id VARCHAR,
                name VARCHAR NOT NULL
            )
            """
        )
    )

    profile = ProvisioningProfile(name="Default")
    device = Device(
        device_id="device-1",
        external_id="google-device-1",
        name="Device 1",
        device_type="android",
        status="online",
    )
    sqlite_session.add_all(
        [
            AndroidManagementConfig(id=1, enterprise_name="enterprises/acme"),
            profile,
            device,
        ]
    )
    await sqlite_session.flush()

    sqlite_session.add_all(
        [
            DevicePolicy(
                device_id=device.device_id,
                profile_id=profile.id,
                policy_hash="hash",
            ),
            DeviceCommand(
                device_id=device.device_id,
                command="LOCK",
                dedupe_key="dedupe-device-1-lock",
            ),
            DeviceTelemetry(device_id=device.device_id, battery_level=90),
            PolicyState(device_id=device.device_id),
        ]
    )
    await sqlite_session.commit()
    await sqlite_session.execute(
        text("INSERT INTO policies (device_id, name) VALUES (:device_id, :name)"),
        {"device_id": device.device_id, "name": "Legacy policy"},
    )
    await sqlite_session.commit()

    service = MDMService(DeviceRepository(sqlite_session))

    removed = await service.remove_device(
        "device-1",
        actor_id="admin@example.com",
        user_id=1,
    )

    assert removed is True
    assert deleted_devices == ["enterprises/acme/devices/google-device-1"]
    assert await table_count(sqlite_session, Device) == 0
    assert await table_count(sqlite_session, DevicePolicy) == 0
    assert await table_count(sqlite_session, DeviceCommand) == 0
    assert await table_count(sqlite_session, DeviceTelemetry) == 0
    assert await table_count(sqlite_session, PolicyState) == 0
    assert await legacy_policy_count(sqlite_session) == 0
