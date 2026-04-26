import uuid
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class SigningSession(Base):
    __tablename__ = "signing_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signature_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signatory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signatories.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Secure token (URL-safe, single-use intent)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)

    # Session lifecycle
    status: Mapped[str] = mapped_column(String(50), default="active")
    # active | used | expired | invalidated

    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    # OTP state
    otp_code_hash: Mapped[str | None] = mapped_column(String(255))
    otp_sent_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    otp_attempts: Mapped[int] = mapped_column(default=0)
    otp_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Signing result
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    signed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    # Request context for evidence
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    # TSP response
    tsp_transaction_id: Mapped[str | None] = mapped_column(String(255))
    tsp_response: Mapped[dict | None] = mapped_column(JSON)

    # Relationships
    signature_request: Mapped["SignatureRequest"] = relationship("SignatureRequest", back_populates="signing_sessions")
    signatory: Mapped["Signatory"] = relationship("Signatory", back_populates="signing_sessions")
