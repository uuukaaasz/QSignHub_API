import uuid
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    signature_request_id: Optional[uuid.UUID] = None
    actor_type: str
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    event: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
