import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Document
from app.config import get_settings

settings = get_settings()
pytestmark = pytest.mark.asyncio


async def _create_document(db: AsyncSession, org_id) -> Document:
    import hashlib
    doc = Document(
        organization_id=org_id,
        filename="contract.pdf",
        original_filename="contract.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        storage_key=f"orgs/{org_id}/documents/test/contract.pdf",
        storage_bucket=settings.S3_BUCKET_DOCUMENTS,
        checksum_sha256=hashlib.sha256(b"fake pdf content").hexdigest(),
        status="ready",
    )
    db.add(doc)
    await db.flush()
    return doc


async def test_create_signature_request(client: AsyncClient, db: AsyncSession, org, api_headers):
    doc = await _create_document(db, org.id)

    resp = await client.post("/api/v1/signature-requests", headers=api_headers, json={
        "title": "Umowa o pracę",
        "message": "Proszę o podpisanie umowy.",
        "signature_level": "QES",
        "signature_format": "PAdES",
        "signing_order": "parallel",
        "document_ids": [str(doc.id)],
        "signatories": [
            {
                "email": "jan.kowalski@example.com",
                "full_name": "Jan Kowalski",
                "phone": "+48600000001",
                "role": "signer",
                "identity_verification": "sms_otp",
            }
        ],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Umowa o pracę"
    assert data["status"] == "draft"
    assert data["signature_level"] == "QES"
    assert len(data["signatories"]) == 1
    return data


async def test_send_signature_request(client: AsyncClient, db: AsyncSession, org, api_headers):
    doc = await _create_document(db, org.id)

    create_resp = await client.post("/api/v1/signature-requests", headers=api_headers, json={
        "title": "Test Request",
        "signature_level": "AES",
        "signature_format": "PAdES",
        "signing_order": "parallel",
        "document_ids": [str(doc.id)],
        "signatories": [{"email": "signer@example.com", "full_name": "Anna Nowak", "role": "signer"}],
    })
    assert create_resp.status_code == 201
    req_id = create_resp.json()["id"]

    send_resp = await client.post(f"/api/v1/signature-requests/{req_id}/send", headers=api_headers)
    assert send_resp.status_code == 200
    assert send_resp.json()["status"] == "pending"


async def test_cancel_signature_request(client: AsyncClient, db: AsyncSession, org, api_headers):
    doc = await _create_document(db, org.id)
    create_resp = await client.post("/api/v1/signature-requests", headers=api_headers, json={
        "title": "To be cancelled",
        "signature_level": "SES",
        "signature_format": "PAdES",
        "signing_order": "parallel",
        "document_ids": [str(doc.id)],
        "signatories": [{"email": "x@example.com", "full_name": "X Y", "role": "signer"}],
    })
    req_id = create_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v1/signature-requests/{req_id}/cancel",
        headers=api_headers,
        json={"reason": "Test cancellation"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


async def test_list_signature_requests(client: AsyncClient, db: AsyncSession, org, api_headers):
    doc = await _create_document(db, org.id)
    await client.post("/api/v1/signature-requests", headers=api_headers, json={
        "title": "List test",
        "signature_level": "QES",
        "signature_format": "PAdES",
        "signing_order": "parallel",
        "document_ids": [str(doc.id)],
        "signatories": [{"email": "a@b.com", "full_name": "A B", "role": "signer"}],
    })
    resp = await client.get("/api/v1/signature-requests", headers=api_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_get_nonexistent_request_returns_404(client: AsyncClient, api_headers):
    import uuid
    resp = await client.get(f"/api/v1/signature-requests/{uuid.uuid4()}", headers=api_headers)
    assert resp.status_code == 404
