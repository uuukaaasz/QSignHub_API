import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_webhook(client: AsyncClient, api_headers):
    resp = await client.post("/api/v1/webhooks", headers=api_headers, json={
        "url": "https://example.com/webhook",
        "events": ["signature_request.completed", "signatory.signed"],
        "description": "Production webhook",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["url"] == "https://example.com/webhook"
    assert "id" in data
    assert data["is_active"] is True


async def test_list_webhooks(client: AsyncClient, api_headers):
    await client.post("/api/v1/webhooks", headers=api_headers, json={
        "url": "https://example.com/wh1",
        "events": [],
    })
    resp = await client.get("/api/v1/webhooks", headers=api_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_update_webhook(client: AsyncClient, api_headers):
    create = await client.post("/api/v1/webhooks", headers=api_headers, json={
        "url": "https://example.com/old",
        "events": [],
    })
    wh_id = create.json()["id"]

    resp = await client.patch(f"/api/v1/webhooks/{wh_id}", headers=api_headers, json={
        "url": "https://example.com/new",
        "is_active": False,
    })
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://example.com/new"
    assert resp.json()["is_active"] is False


async def test_delete_webhook(client: AsyncClient, api_headers):
    create = await client.post("/api/v1/webhooks", headers=api_headers, json={
        "url": "https://example.com/to-delete",
        "events": [],
    })
    wh_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/webhooks/{wh_id}", headers=api_headers)
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/webhooks/{wh_id}", headers=api_headers)
    assert get_resp.status_code == 404


async def test_unauthorized_webhook_access(client: AsyncClient):
    resp = await client.get("/api/v1/webhooks")
    assert resp.status_code == 401
