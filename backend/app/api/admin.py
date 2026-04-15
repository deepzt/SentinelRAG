import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter()

_ADMIN_ROLES = {"manager", "admin"}


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    query: str
    retrieved_doc_ids: list
    response_time_ms: int | None
    access_decision: str
    created_at: datetime


class AuditReportResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
    denied_count: int
    allowed_count: int


@router.get("/audit-report", response_model=AuditReportResponse)
async def audit_report(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    decision_filter: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
) -> AuditReportResponse:
    """Return paginated audit log. Manager/admin role only.

    Supports filtering by access_decision ('allowed' | 'denied').
    """
    base = select(AuditLog)
    if decision_filter in ("allowed", "denied", "error"):
        base = base.where(AuditLog.access_decision == decision_filter)

    total_result = await db.execute(
        select(func.count()).select_from(base.subquery())
    )
    total = total_result.scalar_one()

    denied_result = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.access_decision == "denied")
    )
    denied_count = denied_result.scalar_one()

    allowed_result = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.access_decision == "allowed")
    )
    allowed_count = allowed_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
    )
    logs = result.scalars().all()

    return AuditReportResponse(
        items=[AuditLogEntry.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        denied_count=denied_count,
        allowed_count=allowed_count,
    )
