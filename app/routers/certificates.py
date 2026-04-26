import uuid
import math
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func
from app.models import Certificate
from app.schemas.certificate import (
    CertificateResponse,
    CertificateValidationRequest,
    CertificateValidationResponse,
)
from app.schemas.common import PaginatedResponse
from app.dependencies import DBSession, ApiKeyAuth, Pages
from app.services.certificate_service import CertificateService

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.get("", response_model=PaginatedResponse[CertificateResponse])
async def list_certificates(db: DBSession, ctx: ApiKeyAuth, pagination: Pages):
    total = await db.scalar(
        select(func.count()).select_from(Certificate).where(Certificate.organization_id == ctx.org_id)
    )
    result = await db.execute(
        select(Certificate)
        .where(Certificate.organization_id == ctx.org_id)
        .order_by(Certificate.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    return PaginatedResponse(
        data=result.scalars().all(),
        total=total or 0,
        page=pagination.page,
        per_page=pagination.per_page,
        pages=math.ceil((total or 0) / pagination.per_page),
    )


@router.get("/{cert_id}", response_model=CertificateResponse)
async def get_certificate(cert_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    cert = await db.get(Certificate, cert_id)
    if not cert or cert.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return cert


@router.post("/validate", response_model=CertificateValidationResponse)
async def validate_certificate(payload: CertificateValidationRequest, db: DBSession, ctx: ApiKeyAuth):
    """
    Validate a PEM-encoded X.509 certificate.
    Checks expiry, revocation (OCSP), trust chain, and eIDAS qualification level.
    """
    svc = CertificateService()
    result = await svc.validate_certificate(payload.certificate_pem, payload.check_revocation)

    # Persist validated cert if it's new
    if result.is_valid and result.fingerprint_sha256 if hasattr(result, 'fingerprint_sha256') else False:
        pass  # upsert logic here in production

    return result
