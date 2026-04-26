import uuid
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class SigningSessionResponse(BaseModel):
    id: uuid.UUID
    token: str
    signing_url: str
    status: str
    expires_at: datetime
    is_completed: bool
    signatory_id: uuid.UUID
    signature_request_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class SigningSessionPublic(BaseModel):
    """Minimal session info for the signing page (no internal IDs leaked)."""
    token: str
    status: str
    expires_at: datetime
    is_completed: bool
    requires_otp: bool
    signatory_name: str
    signatory_email: str
    request_title: str
    request_message: Optional[str] = None
    signature_level: str
    redirect_url: Optional[str] = None


class OtpRequest(BaseModel):
    """Trigger OTP send."""
    channel: str = "sms"  # sms | email


class OtpVerify(BaseModel):
    code: str


class CompleteSigningRequest(BaseModel):
    consent: bool = True
    # For SES/AES: drawn signature image (base64) or typed name
    signature_image_b64: Optional[str] = None
    typed_name: Optional[str] = None
    # For QES: TSP token received from external flow
    tsp_token: Optional[str] = None
