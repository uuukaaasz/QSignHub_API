import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_creates_org_and_owner(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "organization_name": "Acme Corp",
        "email": "ceo@acme.com",
        "full_name": "Jan Kowalski",
        "password": "Str0ng!Pass",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_register_duplicate_email_returns_409(client: AsyncClient):
    payload = {
        "organization_name": "Dup Corp",
        "email": "dup@test.com",
        "full_name": "Test User",
        "password": "Str0ng!Pass",
    }
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


async def test_login_valid_credentials(client: AsyncClient, owner):
    resp = await client.post("/api/v1/auth/token", json={
        "email": owner.email,
        "password": "Str0ngP@ss!",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password(client: AsyncClient, owner):
    resp = await client.post("/api/v1/auth/token", json={
        "email": owner.email,
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


async def test_refresh_token(client: AsyncClient, owner):
    login = await client.post("/api/v1/auth/token", json={
        "email": owner.email, "password": "Str0ngP@ss!"
    })
    refresh_token = login.json()["refresh_token"]
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_protected_endpoint_without_token(client: AsyncClient):
    resp = await client.get("/api/v1/organizations/me")
    assert resp.status_code == 401


async def test_protected_endpoint_with_valid_token(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/organizations/me", headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()
