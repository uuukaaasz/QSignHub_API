import uuid
from sqlalchemy import String, ForeignKey, DateTime, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Certificate identity
    subject_dn: Mapped[str] = mapped_column(Text, nullable=False)
    issuer_dn: Mapped[str] = mapped_column(Text, nullable=False)
    serial_number: Mapped[str] = mapped_column(String(255), nullable=False)
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # Type & level
    certificate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # qualified | advanced | simple | tsa | ca
    level: Mapped[str] = mapped_column(String(10), default="QES")

    # Trust chain
    tsp_name: Mapped[str | None] = mapped_column(String(255))  # e.g. Certum, KIR, Asseco
    tsp_country: Mapped[str | None] = mapped_column(String(2))

    # Validity
    valid_from: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(100))

    # OCSP / CRL
    ocsp_url: Mapped[str | None] = mapped_column(Text)
    crl_url: Mapped[str | None] = mapped_column(Text)
    last_ocsp_check_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    ocsp_status: Mapped[str | None] = mapped_column(String(20))  # good | revoked | unknown

    # Raw PEM
    certificate_pem: Mapped[str] = mapped_column(Text, nullable=False)
    chain_pem: Mapped[str | None] = mapped_column(Text)

    # Parsed fields
    parsed_data: Mapped[dict | None] = mapped_column(JSON)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="certificates")
