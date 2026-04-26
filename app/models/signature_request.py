import uuid
from sqlalchemy import String, ForeignKey, DateTime, Text, Boolean, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class SignatureRequest(Base):
    __tablename__ = "signature_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(String(255), index=True)  # caller's own ID

    # Signature parameters (eIDAS levels)
    signature_level: Mapped[str] = mapped_column(String(10), default="QES")
    # QES = Qualified Electronic Signature
    # AES = Advanced Electronic Signature
    # SES = Simple Electronic Signature
    signature_format: Mapped[str] = mapped_column(String(10), default="PAdES")
    # PAdES (PDF), XAdES (XML), CAdES (CMS)

    # Signing order
    signing_order: Mapped[str] = mapped_column(String(20), default="parallel")
    # parallel | sequential

    # Status lifecycle
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    # draft | pending | in_progress | completed | declined | cancelled | expired

    # Deadlines
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    cancelled_reason: Mapped[str | None] = mapped_column(Text)

    # Notifications
    send_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_interval_days: Mapped[int] = mapped_column(Integer, default=3)
    notify_on_signed: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_completed: Mapped[bool] = mapped_column(Boolean, default=True)
    requester_email: Mapped[str | None] = mapped_column(String(255))
    requester_name: Mapped[str | None] = mapped_column(String(255))

    # Redirect after signing
    redirect_url: Mapped[str | None] = mapped_column(Text)

    # Additional metadata
    metadata: Mapped[dict | None] = mapped_column(JSON)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="signature_requests")
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="signature_request", foreign_keys="Document.signature_request_id"
    )
    signatories: Mapped[list["Signatory"]] = relationship(
        "Signatory", back_populates="signature_request", cascade="all, delete-orphan"
    )
    signing_sessions: Mapped[list["SigningSession"]] = relationship(
        "SigningSession", back_populates="signature_request", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="signature_request"
    )
