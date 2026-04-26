import uuid
import math
import secrets
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func
from app.models import Webhook, WebhookDelivery
from app.schemas.webhook import WebhookCreate, WebhookResponse, WebhookUpdate, WebhookDeliveryResponse
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.dependencies import DBSession, ApiKeyAuth, Pages

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(db: DBSession, ctx: ApiKeyAuth):
    result = await db.execute(
        select(Webhook)
        .where(Webhook.organization_id == ctx.org_id)
        .order_by(Webhook.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(payload: WebhookCreate, db: DBSession, ctx: ApiKeyAuth):
    webhook = Webhook(
        organization_id=ctx.org_id,
        url=payload.url,
        secret=secrets.token_hex(32),
        events=payload.events,
        description=payload.description,
        is_active=True,
    )
    db.add(webhook)
    await db.flush()
    return webhook


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(webhook_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    wh = await db.get(Webhook, webhook_id)
    if not wh or wh.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return wh


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: uuid.UUID, payload: WebhookUpdate, db: DBSession, ctx: ApiKeyAuth
):
    wh = await db.get(Webhook, webhook_id)
    if not wh or wh.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(wh, field, value)
    await db.flush()
    return wh


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(webhook_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    wh = await db.get(Webhook, webhook_id)
    if not wh or wh.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    await db.delete(wh)
    await db.flush()


@router.post("/{webhook_id}/test", response_model=SuccessResponse)
async def test_webhook(webhook_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth):
    """Send a test event to the webhook URL."""
    from app.services.webhook_service import WebhookService
    wh = await db.get(Webhook, webhook_id)
    if not wh or wh.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    svc = WebhookService(db)
    await svc.dispatch("webhook.test", {"message": "This is a test event from QSignHub"}, ctx.org_id)
    return SuccessResponse(message="Test event dispatched")


@router.get("/{webhook_id}/deliveries", response_model=PaginatedResponse[WebhookDeliveryResponse])
async def list_deliveries(webhook_id: uuid.UUID, db: DBSession, ctx: ApiKeyAuth, pagination: Pages):
    wh = await db.get(Webhook, webhook_id)
    if not wh or wh.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    total = await db.scalar(
        select(func.count()).select_from(WebhookDelivery).where(WebhookDelivery.webhook_id == webhook_id)
    )
    result = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
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
