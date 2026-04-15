from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.core.limiter import limiter
from app.models.user import User
from app.rag.schemas import QueryRequest, QueryResponse
from app.rag.service import handle_query

router = APIRouter()


@router.post("", response_model=QueryResponse)
@limiter.limit("30/minute")
async def query(
    request: Request,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryResponse:
    """Submit a query to the RBAC-filtered RAG pipeline.

    - Requires a valid Bearer token.
    - Rate limited to 30 requests per minute per IP.
    - Returns only documents the authenticated user's role can access.
    - Writes an audit log row regardless of access decision.
    - Citations include document title, section, and department.
    """
    return await handle_query(db, request=body, current_user=current_user)
