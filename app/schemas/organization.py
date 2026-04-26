import uuid
from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, Dict, Any
from datetime import datetime


class AddressSchema(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "PL"


class BrandingSchema(BaseModel):
    primary_color: Optional[str] = None
    logo_url: Optional[str] = None
    company_name: Optional[str] = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    email: str
    phone: Optional[str] = None
    website: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[AddressSchema] = None
    logo_url: Optional[str] = None
    plan: str
    monthly_signature_limit: int
    signatures_used_this_month: int
    default_signature_level: str
    default_locale: str
    require_sms_otp: bool
    branding: Optional[BrandingSchema] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[AddressSchema] = None
    branding: Optional[BrandingSchema] = None
    default_signature_level: Optional[str] = None
    default_locale: Optional[str] = None
    require_sms_otp: Optional[bool] = None
