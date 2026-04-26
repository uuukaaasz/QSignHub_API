import uuid
from sqlalchemy import String, BigInteger, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signature_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="SET NULL"), index=True
    )

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[int | None] = mapped_column()

    # Storage
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    storage_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="uploaded")
    # uploaded | processing | ready | signed | archived

    # Signed document info (populated after signing)
    signed_storage_key: Mapped[str | None] = mapped_column(Text)
    signature_format: Mapped[str | None] = mapped_column(String(20))  # PAdES | XAdES | CAdES

    # Field positions for visual signature placement
    signature_fields: Mapped[list | None] = mapped_column(JSON)

    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata: Mapped[dict | None] = mapped_column(JSON)

    # Relationships
    signature_request: Mapped["SignatureRequest | None"] = relationship(
        "SignatureRequest", back_populates="documents", foreign_keys=[signature_request_id]
    )
