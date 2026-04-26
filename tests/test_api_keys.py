import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_api_key(client: AsyncClient, auth_headers):
    resp = await client.post("/api/v1/api-keys", headers=auth_headers, json={
        "name": "Production Key",
        "environment": "live",
        "description": "Used by our backend",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "key" in data  # raw key shown only once
    assert data["key"].startswith("qsh_live_")
    assert data["environment"] == "live"


async def test_list_api_keys(client: AsyncClient, auth_headers):
    resp = await client.get("/api/v1/api-keys", headers=auth_headers)
    assert resp.status_code == 200
    assert "data" in resp.json()
    assert "total" in resp.json()


async def test_revoke_api_key(client: AsyncClient, auth_headers):
    create = await client.post("/api/v1/api-keys", headers=auth_headers, json={
        "name": "To revoke",
        "environment": "test",
    })
    key_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/api-keys/{key_id}", headers=auth_headers)
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/api-keys/{key_id}", headers=auth_headers)
    assert get_resp.json()["is_active"] is False


async def test_raw_key_usable_immediately(client: AsyncClient, auth_headers):
    create = await client.post("/api/v1/api-keys", headers=auth_headers, json={
        "name": "Usable key",
        "environment": "live",
    })
    raw_key = create.json()["key"]
    resp = await client.get("/api/v1/documents", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200
