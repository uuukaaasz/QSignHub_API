import uuid
from sqlalchemy import String, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signature_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="SET NULL"), index=True
    )

    # Who
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # user | signatory | system | api_key
    actor_id: Mapped[str | None] = mapped_column(String(255))
    actor_email: Mapped[str | None] = mapped_column(String(255))

    # What
    event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. signature_request.created, signatory.signed, document.downloaded

    # Context
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    metadata: Mapped[dict | None] = mapped_column(JSON)

    # Request context
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    # Tamper evidence: hash of this log entry
    entry_hash: Mapped[str | None] = mapped_column(String(64))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="audit_logs")
    signature_request: Mapped["SignatureRequest | None"] = relationship(
        "SignatureRequest", back_populates="audit_logs"
    )
