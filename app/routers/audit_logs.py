import uuid
import math
from typing import Optional
from fastapi import APIRouter, Query
from sqlalchemy import select, func
from app.models import AuditLog
from app.schemas.audit_log import AuditLogResponse
from app.schemas.common import PaginatedResponse
from app.dependencies import DBSession, ApiKeyAuth, Pages

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    db: DBSession,
    ctx: ApiKeyAuth,
    pagination: Pages,
    signature_request_id: Optional[uuid.UUID] = Query(None),
    event: Optional[str] = Query(None),
    actor_type: Optional[str] = Query(None),
):
    """
    Retrieve immutable audit trail for compliance and forensic purposes.
    All signing events — views, OTPs, signatures, declines — are recorded here.
    """
    query = select(AuditLog).where(AuditLog.organization_id == ctx.org_id)
    if signature_request_id:
        query = query.where(AuditLog.signature_request_id == signature_request_id)
    if event:
        query = query.where(AuditLog.event == event)
    if actor_type:
        query = query.where(AuditLog.actor_type == actor_type)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(AuditLog.created_at.desc())
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


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(log_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    from fastapi import HTTPException, status
    log = await db.get(AuditLog, log_id)
    if not log or log.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log not found")
    return log
