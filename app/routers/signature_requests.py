import uuid
import math
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models import SignatureRequest, Signatory
from app.schemas.signature_request import (
    SignatureRequestCreate,
    SignatureRequestResponse,
    SignatureRequestUpdate,
    SignatureRequestListResponse,
    CancelRequest,
)
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.dependencies import DBSession, ApiKeyAuth, Pages
from app.services.signature_service import SignatureService

router = APIRouter(prefix="/signature-requests", tags=["Signature Requests"])


async def _get_request_or_404(db: DBSession, req_id: uuid.UUID, org_id: uuid.UUID) -> SignatureRequest:
    result = await db.execute(
        select(SignatureRequest)
        .where(SignatureRequest.id == req_id, SignatureRequest.organization_id == org_id)
        .options(
            selectinload(SignatureRequest.documents),
            selectinload(SignatureRequest.signatories),
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signature request not found")
    return req


@router.post("", response_model=SignatureRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_signature_request(
    payload: SignatureRequestCreate,
    db: DBSession,
    ctx: ApiKeyAuth,
):
    """
    Create a new signature request.

    Set `status=draft` on create; call `POST /signature-requests/{id}/send` to dispatch.
    """
    svc = SignatureService(db)
    req = await svc.create_request(ctx.org_id, payload)
    await db.refresh(req, ["documents", "signatories"])
    return req


@router.post("/{req_id}/send", response_model=SignatureRequestResponse)
async def send_signature_request(req_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    """Dispatch signing invitations to all signatories (draft → pending)."""
    req = await _get_request_or_404(db, req_id, ctx.org_id)
    if req.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot send a request with status '{req.status}'",
        )
    svc = SignatureService(db)
    req = await svc.send_request(req)
    await db.refresh(req, ["documents", "signatories"])
    return req


@router.get("", response_model=PaginatedResponse[SignatureRequestListResponse])
async def list_signature_requests(
    db: DBSession,
    ctx: ApiKeyAuth,
    pagination: Pages,
    status_filter: Optional[str] = Query(None, alias="status"),
    reference: Optional[str] = Query(None),
):
    query = select(SignatureRequest).where(SignatureRequest.organization_id == ctx.org_id)
    if status_filter:
        query = query.where(SignatureRequest.status == status_filter)
    if reference:
        query = query.where(SignatureRequest.reference == reference)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(SignatureRequest.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    reqs = result.scalars().all()

    # Build list response with signatory counts
    items = []
    for r in reqs:
        sigs = await db.execute(
            select(Signatory).where(Signatory.signature_request_id == r.id)
        )
        sigs = sigs.scalars().all()
        signers = [s for s in sigs if s.role == "signer"]
        signed = [s for s in signers if s.status == "signed"]
        items.append(
            SignatureRequestListResponse(
                id=r.id,
                title=r.title,
                reference=r.reference,
                signature_level=r.signature_level,
                status=r.status,
                signatories_total=len(signers),
                signatories_signed=len(signed),
                expires_at=r.expires_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )

    return PaginatedResponse(
        data=items,
        total=total or 0,
        page=pagination.page,
        per_page=pagination.per_page,
        pages=math.ceil((total or 0) / pagination.per_page),
    )


@router.get("/{req_id}", response_model=SignatureRequestResponse)
async def get_signature_request(req_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    return await _get_request_or_404(db, req_id, ctx.org_id)


@router.patch("/{req_id}", response_model=SignatureRequestResponse)
async def update_signature_request(
    req_id: uuid.UUID, payload: SignatureRequestUpdate, db: DBSession, ctx: ApiKeyAuth
):
    req = await _get_request_or_404(db, req_id, ctx.org_id)
    if req.status not in ("draft", "pending"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can only update draft or pending requests",
        )
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(req, field, value)
    await db.flush()
    await db.refresh(req, ["documents", "signatories"])
    return req


@router.post("/{req_id}/cancel", response_model=SignatureRequestResponse)
async def cancel_signature_request(
    req_id: uuid.UUID, payload: CancelRequest, db: DBSession, ctx: ApiKeyAuth
):
    req = await _get_request_or_404(db, req_id, ctx.org_id)
    if req.status in ("completed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already {req.status}",
        )
    req.status = "cancelled"
    req.cancelled_at = datetime.now(timezone.utc)
    req.cancelled_reason = payload.reason
    await db.flush()
    await db.refresh(req, ["documents", "signatories"])
    return req


@router.post("/{req_id}/remind", response_model=SuccessResponse)
async def send_reminders(req_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    """Manually trigger reminder emails to pending signatories."""
    req = await _get_request_or_404(db, req_id, ctx.org_id)
    if req.status not in ("pending", "in_progress"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reminders can only be sent for pending/in_progress requests",
        )
    from app.services.notification_service import NotificationService
    from app.models import SigningSession
    notifier = NotificationService()
    sent = 0
    for signatory in req.signatories:
        if signatory.status in ("pending", "sent", "viewed"):
            session_result = await db.execute(
                select(SigningSession)
                .where(
                    SigningSession.signatory_id == signatory.id,
                    SigningSession.status == "active",
                )
                .order_by(SigningSession.created_at.desc())
                .limit(1)
            )
            session = session_result.scalar_one_or_none()
            if session:
                from app.config import get_settings
                s = get_settings()
                url = f"{s.SIGNING_SESSION_BASE_URL}/sign/{session.token}"
                await notifier.send_reminder(signatory, req, url)
                sent += 1
    return SuccessResponse(message=f"Reminders sent to {sent} signatory(ies)")
