"""Chat session endpoints.

POST /chat/sessions          — create a new session for the current user
GET  /chat/sessions/{id}/messages — load message history for a session
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User

router = APIRouter()


class SessionResponse(BaseModel):
    id: uuid.UUID
    session_name: str | None
    created_at: str

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    sender: str
    message: str
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Create a new chat session for the authenticated user."""
    session = ChatSession(user_id=current_user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(
        id=session.id,
        session_name=session.session_name,
        created_at=session.created_at.isoformat(),
    )


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MessageResponse]:
    """Return messages for a session owned by the current user."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session not found")

    msgs = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return [
        MessageResponse(
            id=m.id,
            sender=m.sender,
            message=m.message,
            created_at=m.created_at.isoformat(),
        )
        for m in msgs.scalars().all()
    ]
