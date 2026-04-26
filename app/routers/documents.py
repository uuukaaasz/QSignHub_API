import uuid
import hashlib
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status, Query
from sqlalchemy import select, func
from app.models import Document
from app.schemas.document import DocumentResponse, DocumentDownloadResponse
from app.schemas.common import PaginatedResponse
from app.dependencies import DBSession, ApiKeyAuth, Pages
from app.services.storage_service import StorageService
from app.config import get_settings
import math

settings = get_settings()
router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/xml",
    "text/xml",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: DBSession,
    ctx: ApiKeyAuth,
    file: UploadFile = File(...),
    is_template: bool = Form(False),
):
    """Upload a document to be signed. Returns document ID for use in signature requests."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 50 MB)")

    storage = StorageService()
    storage_key, checksum = await storage.upload_document(
        data, file.filename or "document.pdf", file.content_type, ctx.org_id
    )

    doc = Document(
        organization_id=ctx.org_id,
        filename=file.filename or "document.pdf",
        original_filename=file.filename or "document.pdf",
        mime_type=file.content_type,
        size_bytes=len(data),
        storage_key=storage_key,
        storage_bucket=settings.S3_BUCKET_DOCUMENTS,
        checksum_sha256=checksum,
        status="ready",
        is_template=is_template,
    )
    db.add(doc)
    await db.flush()
    return doc


@router.get("", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    db: DBSession,
    ctx: ApiKeyAuth,
    pagination: Pages,
    is_template: Optional[bool] = Query(None),
    status: Optional[str] = Query(None),
):
    query = select(Document).where(Document.organization_id == ctx.org_id)
    if is_template is not None:
        query = query.where(Document.is_template == is_template)
    if status:
        query = query.where(Document.status == status)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(Document.created_at.desc()).offset(pagination.offset).limit(pagination.per_page)
    )
    docs = result.scalars().all()
    return PaginatedResponse(
        data=docs,
        total=total or 0,
        page=pagination.page,
        per_page=pagination.per_page,
        pages=math.ceil((total or 0) / pagination.per_page),
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    doc = await db.get(Document, doc_id)
    if not doc or doc.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.get("/{doc_id}/download", response_model=DocumentDownloadResponse)
async def download_document(doc_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    doc = await db.get(Document, doc_id)
    if not doc or doc.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage = StorageService()
    bucket = settings.S3_BUCKET_SIGNED if doc.signed_storage_key else settings.S3_BUCKET_DOCUMENTS
    key = doc.signed_storage_key or doc.storage_key
    url = await storage.generate_presigned_url(bucket, key, expires_in=3600, filename=doc.filename)

    return DocumentDownloadResponse(url=url, expires_in=3600, filename=doc.filename)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    doc = await db.get(Document, doc_id)
    if not doc or doc.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.signature_request_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a document attached to a signature request",
        )

    storage = StorageService()
    await storage.delete(doc.storage_bucket, doc.storage_key)
    await db.delete(doc)
    await db.flush()
