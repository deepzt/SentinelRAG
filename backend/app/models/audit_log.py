import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AuditLog(Base):
    """Append-only compliance log.

    No UPDATE or DELETE endpoints exist for this table.
    Every query — allowed AND denied — produces one row.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    # List of chunk UUIDs returned; empty list for denied requests
    retrieved_doc_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    access_decision: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # "allowed" | "denied" | "error"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    user: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="audit_logs", lazy="select"
    )
