import uuid
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class SignatureFieldSchema(BaseModel):
    page: int
    x: float
    y: float
    width: float
    height: float
    signatory_id: Optional[uuid.UUID] = None
    label: Optional[str] = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    page_count: Optional[int] = None
    status: str
    checksum_sha256: str
    signature_format: Optional[str] = None
    signature_fields: Optional[List[SignatureFieldSchema]] = None
    is_template: bool
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(DocumentResponse):
    upload_url: Optional[str] = None


class DocumentDownloadResponse(BaseModel):
    url: str
    expires_in: int  # seconds
    filename: str
