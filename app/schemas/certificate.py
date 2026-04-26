import uuid
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class CertificateResponse(BaseModel):
    id: uuid.UUID
    subject_dn: str
    issuer_dn: str
    serial_number: str
    fingerprint_sha256: str
    certificate_type: str
    level: str
    tsp_name: Optional[str] = None
    tsp_country: Optional[str] = None
    valid_from: datetime
    valid_to: datetime
    is_revoked: bool
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    ocsp_status: Optional[str] = None
    last_ocsp_check_at: Optional[datetime] = None
    parsed_data: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CertificateValidationRequest(BaseModel):
    certificate_pem: str
    check_revocation: bool = True


class CertificateValidationResponse(BaseModel):
    is_valid: bool
    is_qualified: bool
    level: str
    subject_dn: str
    issuer_dn: str
    serial_number: str
    valid_from: datetime
    valid_to: datetime
    is_expired: bool
    is_revoked: bool
    ocsp_status: Optional[str] = None
    tsp_name: Optional[str] = None
    tsp_country: Optional[str] = None
    trust_chain_valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class DocumentValidationRequest(BaseModel):
    """Validate an already-signed document."""
    document_id: uuid.UUID


class SignatureValidationResult(BaseModel):
    is_valid: bool
    signature_level: str
    signer_name: Optional[str] = None
    signer_email: Optional[str] = None
    signed_at: Optional[datetime] = None
    certificate: Optional[CertificateValidationResponse] = None
    document_integrity: bool
    errors: list[str] = []


class DocumentValidationResponse(BaseModel):
    document_id: uuid.UUID
    overall_valid: bool
    signatures: list[SignatureValidationResult] = []
