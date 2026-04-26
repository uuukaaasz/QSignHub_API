import uuid
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from app.models import SignatureRequest, Signatory
from app.schemas.signatory import SignatoryCreate, SignatoryResponse, SignatoryUpdate
from app.dependencies import DBSession, ApiKeyAuth

router = APIRouter(prefix="/signature-requests/{req_id}/signatories", tags=["Signatories"])


async def _get_req(db: DBSession, req_id: uuid.UUID, org_id: uuid.UUID) -> SignatureRequest:
    req = await db.get(SignatureRequest, req_id)
    if not req or req.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signature request not found")
    return req


@router.get("", response_model=list[SignatoryResponse])
async def list_signatories(req_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    await _get_req(db, req_id, ctx.org_id)
    result = await db.execute(
        select(Signatory)
        .where(Signatory.signature_request_id == req_id)
        .order_by(Signatory.order, Signatory.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=SignatoryResponse, status_code=status.HTTP_201_CREATED)
async def add_signatory(req_id: uuid.UUID, payload: SignatoryCreate, db: DBSession, ctx: ApiKeyAuth):
    req = await _get_req(db, req_id, ctx.org_id)
    if req.status not in ("draft",):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can only add signatories to draft requests",
        )
    signatory = Signatory(
        signature_request_id=req_id,
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
        order=payload.order,
        role=payload.role,
        identity_verification=payload.identity_verification,
        metadata=payload.metadata,
        status="pending",
    )
    db.add(signatory)
    await db.flush()
    return signatory


@router.get("/{sig_id}", response_model=SignatoryResponse)
async def get_signatory(req_id: uuid.UUID, sig_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    await _get_req(db, req_id, ctx.org_id)
    sig = await db.get(Signatory, sig_id)
    if not sig or sig.signature_request_id != req_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signatory not found")
    return sig


@router.patch("/{sig_id}", response_model=SignatoryResponse)
async def update_signatory(
    req_id: uuid.UUID, sig_id: uuid.UUID, payload: SignatoryUpdate, db: DBSession, ctx: ApiKeyAuth
):
    req = await _get_req(db, req_id, ctx.org_id)
    if req.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Can only update signatories of draft requests"
        )
    sig = await db.get(Signatory, sig_id)
    if not sig or sig.signature_request_id != req_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signatory not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(sig, field, value)
    await db.flush()
    return sig


@router.delete("/{sig_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_signatory(req_id: uuid.UUID, sig_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    req = await _get_req(db, req_id, ctx.org_id)
    if req.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Can only remove signatories from draft requests"
        )
    sig = await db.get(Signatory, sig_id)
    if not sig or sig.signature_request_id != req_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signatory not found")
    await db.delete(sig)
    await db.flush()
