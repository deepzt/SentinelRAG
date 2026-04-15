from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.rag.schemas import QueryRequest, QueryResponse
from app.rag.service import handle_query

router = APIRouter()


@router.post("", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryResponse:
    """Submit a query to the RBAC-filtered RAG pipeline.

    - Requires a valid Bearer token.
    - Returns only documents the authenticated user's role can access.
    - Writes an audit log row regardless of access decision.
    - Citations include document title, section, and department.
    """
    return await handle_query(db, request=body, current_user=current_user)
