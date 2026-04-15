import uuid

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccessPolicy(Base):
    """Single source of truth for RBAC permissions.

    Maps (role, department) → allowed_classification.
    The retrieval layer JOINs this table rather than using hardcoded role checks.
    """

    __tablename__ = "access_policies"
    __table_args__ = (
        UniqueConstraint("role", "department", name="uq_policy_role_dept"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Comma-separated list of allowed classifications, e.g. "internal,confidential"
    allowed_classification: Mapped[str] = mapped_column(String(200), nullable=False)
