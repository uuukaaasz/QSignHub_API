import uuid
from sqlalchemy import String, ForeignKey, DateTime, Integer, Boolean, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Signatory(Base):
    __tablename__ = "signatories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signature_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signature_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Contact info
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))  # for SMS OTP

    # Signing order (used when signing_order=sequential)
    order: Mapped[int] = mapped_column(Integer, default=1)

    # Role / action required
    role: Mapped[str] = mapped_column(String(50), default="signer")
    # signer | approver | cc (copy only)

    # Identity verification
    identity_verification: Mapped[str] = mapped_column(String(50), default="email")
    # email | sms_otp | eid | video_id | bank_id

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")
    # pending | sent | viewed | signed | declined | bounced

    # Timestamps
    sent_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    viewed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    signed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    decline_reason: Mapped[str | None] = mapped_column(Text)

    # Signing evidence (for audit)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    geolocation: Mapped[dict | None] = mapped_column(JSON)
    certificate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("certificates.id"))

    # OTP verification
    otp_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    otp_verified_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    # Custom fields / extra metadata
    metadata: Mapped[dict | None] = mapped_column(JSON)

    # Relationships
    signature_request: Mapped["SignatureRequest"] = relationship("SignatureRequest", back_populates="signatories")
    signing_sessions: Mapped[list["SigningSession"]] = relationship("SigningSession", back_populates="signatory")
    certificate: Mapped["Certificate | None"] = relationship("Certificate", foreign_keys=[certificate_id])
