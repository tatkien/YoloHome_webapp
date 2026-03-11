import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_secret
from app.db.session import Base, get_db
from app.main import app
from app.models.user import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_ADMIN_PASSWORD = "kiendeptrai"


@pytest_asyncio.fixture(scope="function")
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def admin_headers(client: AsyncClient, test_db: AsyncSession) -> dict[str, str]:
    """Seed the admin user directly into the test DB, then return auth headers."""
    admin = User(
        username="admin",
        full_name="Administrator",
        hashed_password=hash_secret(_ADMIN_PASSWORD),
        role="admin",
        is_active=True,
    )
    test_db.add(admin)
    await test_db.commit()

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": _ADMIN_PASSWORD},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_can_create_user_and_read_profile(client, admin_headers):

    create_user_response = await client.post(
        "/api/v1/users/",
        headers=admin_headers,
        json={
            "username": "operator",
            "password": "secret123",
            "full_name": "Operator",
            "role": "user",
        },
    )
    assert create_user_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "secret123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    profile_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["username"] == "operator"


@pytest.mark.asyncio
async def test_user_can_create_own_device(client, admin_headers):
    # Create a second regular user
    user_response = await client.post(
        "/api/v1/users/",
        headers=admin_headers,
        json={"username": "viewer", "password": "secret123", "role": "user"},
    )
    assert user_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "secret123"},
    )
    token = login_response.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {token}"}

    # Regular user should be able to create their own device
    response = await client.post(
        "/api/v1/devices/",
        headers=user_headers,
        json={"name": "Lab Sensor", "device_type": "light"},
    )
    assert response.status_code == 201
    assert response.json()["device_type"] == "light"

    # The device should appear in their own list
    list_response = await client.get("/api/v1/devices/", headers=user_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    # Admin's device list should be separate (empty unless admin created one too)
    admin_list = await client.get("/api/v1/devices/", headers=admin_headers)
    assert len(admin_list.json()) == 0


@pytest.mark.asyncio
async def test_device_feed_telemetry_and_command_flow(client, admin_headers):
    device_response = await client.post(
        "/api/v1/devices/",
        headers=admin_headers,
        json={"name": "Living Room Sensor", "device_type": "light", "description": "Temperature kit"},
    )
    assert device_response.status_code == 201
    device_data = device_response.json()

    feed_response = await client.post(
        "/api/v1/feeds/",
        headers=admin_headers,
        json={
            "device_id": device_data["id"],
            "name": "Temperature",
            "key": "temperature",
            "data_type": "number",
        },
    )
    assert feed_response.status_code == 201
    feed_data = feed_response.json()

    ingest_response = await client.post(
        f"/api/v1/feeds/{feed_data['id']}/ingest",
        headers={"X-Device-Key": device_data["device_key"]},
        json={"value": "28.4"},
    )
    assert ingest_response.status_code == 201
    assert ingest_response.json()["source"] == "device"

    values_response = await client.get(
        f"/api/v1/feeds/{feed_data['id']}/values",
        headers=admin_headers,
    )
    assert values_response.status_code == 200
    assert values_response.json()[0]["value"] == "28.4"

    command_response = await client.post(
        f"/api/v1/devices/{device_data['id']}/commands",
        headers=admin_headers,
        json={"feed_id": feed_data["id"], "payload": {"state": "on"}},
    )
    assert command_response.status_code == 201
    command_data = command_response.json()

    pending_response = await client.get(
        f"/api/v1/devices/{device_data['id']}/commands/pending",
        headers={"X-Device-Key": device_data["device_key"]},
    )
    assert pending_response.status_code == 200
    assert pending_response.json()[0]["status"] == "delivered"

    ack_response = await client.patch(
        f"/api/v1/devices/{device_data['id']}/commands/{command_data['id']}/ack",
        headers={"X-Device-Key": device_data["device_key"]},
        json={"result": {"applied": True}},
    )
    assert ack_response.status_code == 200
    assert ack_response.json()["status"] == "acknowledged"
    assert ack_response.json()["result"] == {"applied": True}


@pytest.mark.asyncio
async def test_dashboard_creation_and_widget_assignment(client, admin_headers):
    device_response = await client.post(
        "/api/v1/devices/",
        headers=admin_headers,
        json={"name": "Control Hub", "device_type": "fan"},
    )
    device_id = device_response.json()["id"]

    feed_response = await client.post(
        "/api/v1/feeds/",
        headers=admin_headers,
        json={"device_id": device_id, "name": "Power", "key": "power"},
    )
    feed_id = feed_response.json()["id"]

    dashboard_response = await client.post(
        "/api/v1/dashboards/",
        headers=admin_headers,
        json={"name": "Main Dashboard", "description": "Overview"},
    )
    assert dashboard_response.status_code == 201
    dashboard_id = dashboard_response.json()["id"]

    widget_response = await client.post(
        f"/api/v1/dashboards/{dashboard_id}/widgets",
        headers=admin_headers,
        json={
            "feed_id": feed_id,
            "title": "Power Switch",
            "widget_type": "toggle",
            "width": 6,
            "height": 4,
            "config": {"color": "green"},
        },
    )
    assert widget_response.status_code == 201

    read_response = await client.get(
        f"/api/v1/dashboards/{dashboard_id}",
        headers=admin_headers,
    )
    assert read_response.status_code == 200
    assert len(read_response.json()["widgets"]) == 1
    assert read_response.json()["widgets"][0]["widget_type"] == "toggle"