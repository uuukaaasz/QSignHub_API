import uuid
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime


class SignatoryCreate(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    order: int = 1
    role: str = "signer"  # signer | approver | cc
    identity_verification: str = "email"  # email | sms_otp | eid | video_id | bank_id
    metadata: Optional[Dict[str, Any]] = None


class SignatoryUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    order: Optional[int] = None
    identity_verification: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SignatoryResponse(BaseModel):
    id: uuid.UUID
    signature_request_id: uuid.UUID
    email: str
    full_name: str
    phone: Optional[str] = None
    order: int
    role: str
    identity_verification: str
    status: str
    sent_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    signed_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    decline_reason: Optional[str] = None
    otp_verified: bool
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}
