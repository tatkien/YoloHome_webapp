"""
Basic smoke tests for the FastAPI application.
These tests use an in-memory SQLite database so no real PostgreSQL is required.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_items_empty(client):
    response = await client.get("/api/v1/items/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_item(client):
    payload = {"name": "Test Item", "description": "A test item"}
    response = await client.post("/api/v1/items/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Item"
    assert data["description"] == "A test item"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_get_item(client):
    create_response = await client.post("/api/v1/items/", json={"name": "Item A"})
    item_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Item A"


@pytest.mark.asyncio
async def test_get_item_not_found(client):
    response = await client.get("/api/v1/items/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_item(client):
    create_response = await client.post("/api/v1/items/", json={"name": "Old Name"})
    item_id = create_response.json()["id"]

    response = await client.put(f"/api/v1/items/{item_id}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_item(client):
    create_response = await client.post("/api/v1/items/", json={"name": "To Delete"})
    item_id = create_response.json()["id"]

    delete_response = await client.delete(f"/api/v1/items/{item_id}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/items/{item_id}")
    assert get_response.status_code == 404
