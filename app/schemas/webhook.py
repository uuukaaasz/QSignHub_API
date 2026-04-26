import uuid
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime

WEBHOOK_EVENTS = [
    "signature_request.created",
    "signature_request.sent",
    "signature_request.completed",
    "signature_request.declined",
    "signature_request.cancelled",
    "signature_request.expired",
    "signatory.viewed",
    "signatory.signed",
    "signatory.declined",
    "document.signed",
]


class WebhookCreate(BaseModel):
    url: str
    events: List[str] = []  # empty = all events
    description: Optional[str] = None


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    events: List[str]
    description: Optional[str] = None
    is_active: bool
    last_triggered_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    consecutive_failures: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryResponse(BaseModel):
    id: uuid.UUID
    webhook_id: uuid.UUID
    event_type: str
    payload: Dict[str, Any]
    http_status: Optional[int] = None
    response_body: Optional[str] = None
    duration_ms: Optional[int] = None
    status: str
    attempts: int
    next_retry_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookEventPayload(BaseModel):
    """Envelope sent in each webhook delivery."""
    id: str  # delivery UUID
    event: str
    created_at: datetime
    organization_id: str
    data: Dict[str, Any]
    api_version: str = "2024-01"
