import uuid
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.signatory import SignatoryCreate, SignatoryResponse
from app.schemas.document import DocumentResponse


class SignatureRequestCreate(BaseModel):
    title: str
    message: Optional[str] = None
    reference: Optional[str] = None

    # Signature parameters
    signature_level: str = "QES"  # QES | AES | SES
    signature_format: str = "PAdES"  # PAdES | XAdES | CAdES
    signing_order: str = "parallel"  # parallel | sequential

    # Documents
    document_ids: List[uuid.UUID]

    # Signatories
    signatories: List[SignatoryCreate]

    # Expiry & notifications
    expires_at: Optional[datetime] = None
    send_reminders: bool = True
    reminder_interval_days: int = 3
    notify_on_signed: bool = True
    notify_on_completed: bool = True
    requester_email: Optional[EmailStr] = None
    requester_name: Optional[str] = None
    redirect_url: Optional[str] = None

    metadata: Optional[Dict[str, Any]] = None


class SignatureRequestUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    expires_at: Optional[datetime] = None
    send_reminders: Optional[bool] = None
    reminder_interval_days: Optional[int] = None
    redirect_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SignatureRequestResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    message: Optional[str] = None
    reference: Optional[str] = None
    signature_level: str
    signature_format: str
    signing_order: str
    status: str
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancelled_reason: Optional[str] = None
    send_reminders: bool
    reminder_interval_days: int
    notify_on_signed: bool
    notify_on_completed: bool
    requester_email: Optional[str] = None
    requester_name: Optional[str] = None
    redirect_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    documents: List[DocumentResponse] = []
    signatories: List[SignatoryResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SignatureRequestListResponse(BaseModel):
    id: uuid.UUID
    title: str
    reference: Optional[str] = None
    signature_level: str
    status: str
    signatories_total: int
    signatories_signed: int
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CancelRequest(BaseModel):
    reason: Optional[str] = None
