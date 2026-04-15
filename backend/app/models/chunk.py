import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # VECTOR(384) — locked to all-MiniLM-L6-v2; changing dimension requires
    # dropping this column and re-embedding all documents.
    embedding: Mapped[list | None] = mapped_column(Vector(384), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # RBAC gate — every retrieval query filters on this column
    role_required: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    # Rich metadata for filtering, analytics, and future hybrid search
    # Expected shape: {department, doc_type, security_level, source_file,
    #                  section_header, tags, chunk_index}
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship(  # noqa: F821
        back_populates="chunks", lazy="select"
    )
