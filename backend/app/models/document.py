import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "pdf" | "markdown"
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    classification: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "internal" | "confidential" | "public"
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    uploader: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="documents", lazy="select"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(  # noqa: F821
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select",
    )
