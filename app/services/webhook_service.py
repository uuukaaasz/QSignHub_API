import uuid
import json
import hmac
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Webhook, WebhookDelivery
from app.config import get_settings

settings = get_settings()


class WebhookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def dispatch(
        self,
        event: str,
        data: Dict[str, Any],
        org_id: uuid.UUID,
    ) -> None:
        """Find matching webhooks and schedule delivery."""
        result = await self.db.execute(
            select(Webhook).where(
                Webhook.organization_id == org_id,
                Webhook.is_active == True,
            )
        )
        webhooks = result.scalars().all()

        for webhook in webhooks:
            if webhook.events and event not in webhook.events:
                continue
            await self._deliver(webhook, event, data, org_id)

    async def _deliver(
        self, webhook: Webhook, event: str, data: Dict[str, Any], org_id: uuid.UUID
    ) -> None:
        delivery_id = str(uuid.uuid4())
        payload = {
            "id": delivery_id,
            "event": event,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "organization_id": str(org_id),
            "api_version": "2024-01",
            "data": data,
        }
        body = json.dumps(payload, default=str)
        signature = self._sign(body, webhook.secret)

        delivery = WebhookDelivery(
            id=uuid.UUID(delivery_id),
            webhook_id=webhook.id,
            event_type=event,
            payload=payload,
            status="pending",
            attempts=0,
        )
        self.db.add(delivery)
        await self.db.flush()

        # Fire async without blocking the request
        asyncio.create_task(
            self._send_with_retry(delivery.id, webhook.url, body, signature, webhook.secret)
        )

    async def _send_with_retry(
        self,
        delivery_id: uuid.UUID,
        url: str,
        body: str,
        signature: str,
        secret: str,
    ) -> None:
        from app.database import AsyncSessionLocal

        delays = [0, 60, 300, 3600, 86400]  # immediate, 1m, 5m, 1h, 24h
        for attempt, delay in enumerate(delays):
            if delay:
                await asyncio.sleep(delay)
            try:
                start = asyncio.get_event_loop().time()
                async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
                    resp = await client.post(
                        url,
                        content=body,
                        headers={
                            "Content-Type": "application/json",
                            settings.WEBHOOK_SECRET_HEADER: signature,
                            "User-Agent": "QSignHub-Webhooks/1.0",
                        },
                    )
                elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
                success = 200 <= resp.status_code < 300

                async with AsyncSessionLocal() as db:
                    delivery = await db.get(WebhookDelivery, delivery_id)
                    if delivery:
                        delivery.attempts += 1
                        delivery.http_status = resp.status_code
                        delivery.response_body = resp.text[:4096]
                        delivery.duration_ms = elapsed
                        delivery.status = "delivered" if success else "failed"
                        if success:
                            delivery.delivered_at = datetime.now(timezone.utc)
                        await db.commit()
                if success:
                    return
            except Exception as exc:
                async with AsyncSessionLocal() as db:
                    delivery = await db.get(WebhookDelivery, delivery_id)
                    if delivery:
                        delivery.attempts += 1
                        delivery.status = "failed"
                        delivery.response_body = str(exc)[:4096]
                        await db.commit()

    @staticmethod
    def _sign(body: str, secret: str) -> str:
        return "sha256=" + hmac.new(
            secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
