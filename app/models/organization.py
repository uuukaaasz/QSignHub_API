import uuid
from sqlalchemy import String, Boolean, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    website: Mapped[str | None] = mapped_column(String(500))
    tax_id: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[dict | None] = mapped_column(JSON)
    logo_url: Mapped[str | None] = mapped_column(Text)

    # Plan & billing
    plan: Mapped[str] = mapped_column(String(50), default="free")  # free | starter | business | enterprise
    monthly_signature_limit: Mapped[int] = mapped_column(Integer, default=5)
    signatures_used_this_month: Mapped[int] = mapped_column(Integer, default=0)

    # Settings
    branding: Mapped[dict | None] = mapped_column(JSON)  # custom colors, logo for signing page
    default_signature_level: Mapped[str] = mapped_column(String(10), default="QES")
    default_locale: Mapped[str] = mapped_column(String(10), default="pl")
    require_sms_otp: Mapped[bool] = mapped_column(Boolean, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    api_keys: Mapped[list["ApiKey"]] = relationship("ApiKey", back_populates="organization", cascade="all, delete-orphan")
    signature_requests: Mapped[list["SignatureRequest"]] = relationship("SignatureRequest", back_populates="organization", cascade="all, delete-orphan")
    webhooks: Mapped[list["Webhook"]] = relationship("Webhook", back_populates="organization", cascade="all, delete-orphan")
    certificates: Mapped[list["Certificate"]] = relationship("Certificate", back_populates="organization", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="organization", cascade="all, delete-orphan")
