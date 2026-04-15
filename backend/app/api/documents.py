import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.models.access_policy import AccessPolicy
from app.models.document import Document
from app.models.user import User

router = APIRouter()


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_type: str
    department: str
    classification: str
    version: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int
    page: int
    page_size: int


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    """List documents accessible to the authenticated user's role.

    Filters by access_policies — only departments and classifications
    the role is permitted to see are returned.
    """
    # Resolve allowed departments from access_policies
    policy_result = await db.execute(
        select(AccessPolicy.department, AccessPolicy.allowed_classification).where(
            AccessPolicy.role == current_user.role
        )
    )
    policies = policy_result.all()

    if not policies:
        return DocumentListResponse(items=[], total=0, page=page, page_size=page_size)

    # Build filter: document must be in an allowed (department, classification) pair
    from sqlalchemy import or_, and_

    access_filters = []
    for dept, allowed_classifications in policies:
        classifications = [c.strip() for c in allowed_classifications.split(",")]
        access_filters.append(
            and_(
                Document.department == dept,
                Document.classification.in_(classifications),
            )
        )

    base_query = select(Document).where(or_(*access_filters))

    # Count
    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Paginate
    offset = (page - 1) * page_size
    result = await db.execute(
        base_query.order_by(Document.created_at.desc()).offset(offset).limit(page_size)
    )
    docs = result.scalars().all()

    return DocumentListResponse(
        items=[DocumentSummary.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )
