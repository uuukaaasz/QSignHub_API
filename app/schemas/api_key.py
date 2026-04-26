import uuid
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ApiKeyCreate(BaseModel):
    name: str
    environment: str = "live"  # live | test
    scopes: Optional[List[str]] = None
    ip_whitelist: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    description: Optional[str] = None


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    environment: str
    scopes: Optional[List[str]] = None
    ip_whitelist: Optional[List[str]] = None
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned only once at creation — contains the raw key."""
    key: str
