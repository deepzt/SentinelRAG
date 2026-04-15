"""RAG orchestration service.

Flow:
  1. Check access_policies — if role has no policies at all, deny immediately.
  2. Embed the query.
  3. RBAC-filtered pgvector search (role check is at SQL level).
  4. Generate response via LLM.
  5. Write audit log (always — including denied requests).
  6. Return QueryResponse with citations.

This module calls audit/service.py for logging.
It does NOT call ingestion — that is owned by RAG Engineer.
"""

import time
import uuid

from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import write_audit_log
from app.core.config import settings
from app.models.access_policy import AccessPolicy
from app.models.chat import ChatMessage
from app.models.user import User
from app.rag import llm as llm_client
from app.rag.retrieval import rbac_vector_search
from app.rag.schemas import CitationItem, QueryRequest, QueryResponse, RetrievedChunk

# Module-level model load — loaded once at startup, not per request
_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedding_model


def embed_query(query: str) -> list[float]:
    model = get_embedding_model()
    vector = model.encode(query, normalize_embeddings=True)
    return vector.tolist()


async def _save_chat_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_query: str,
    assistant_answer: str,
) -> None:
    """Persist user + assistant turn to chat_messages."""
    db.add(ChatMessage(session_id=session_id, sender="user", message=user_query))
    db.add(ChatMessage(session_id=session_id, sender="assistant", message=assistant_answer))
    await db.commit()


async def _role_has_policies(db: AsyncSession, role: str) -> bool:
    """Return True if the role has at least one access policy row."""
    result = await db.execute(
        select(AccessPolicy.id).where(AccessPolicy.role == role).limit(1)
    )
    return result.scalar_one_or_none() is not None


def _build_citations(chunks: list[RetrievedChunk]) -> list[CitationItem]:
    return [
        CitationItem(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            title=c.title,
            section_header=c.metadata.get("section_header", c.title),
            department=c.metadata.get("department", "unknown"),
            doc_type=c.metadata.get("doc_type", "unknown"),
            score=round(c.score, 4),
        )
        for c in chunks
    ]


async def handle_query(
    db: AsyncSession,
    *,
    request: QueryRequest,
    current_user: User,
) -> QueryResponse:
    """Entry point called by the /query route handler."""
    start_ms = int(time.monotonic() * 1000)

    # 1. Verify role has at least one access policy — deny early if not
    if not await _role_has_policies(db, current_user.role):
        await write_audit_log(
            db,
            user_id=current_user.id,
            query=request.query,
            retrieved_doc_ids=[],
            response_time_ms=int(time.monotonic() * 1000) - start_ms,
            access_decision="denied",
        )
        denial = "Access denied: your role does not have any document access policies configured."
        if request.session_id:
            await _save_chat_messages(db, request.session_id, request.query, denial)
        return QueryResponse(
            query=request.query,
            answer=denial,
            citations=[],
            access_decision="denied",
            chunks_retrieved=0,
            session_id=request.session_id,
        )

    # 2. Embed query
    query_embedding = embed_query(request.query)

    # 3. RBAC-filtered pgvector search
    chunks = await rbac_vector_search(
        db,
        query_embedding=query_embedding,
        user_role=current_user.role,
        top_k=request.top_k,
    )

    elapsed_ms = int(time.monotonic() * 1000) - start_ms

    if not chunks:
        await write_audit_log(
            db,
            user_id=current_user.id,
            query=request.query,
            retrieved_doc_ids=[],
            response_time_ms=elapsed_ms,
            access_decision="denied",
        )
        denial = "No accessible documents were found for your query."
        if request.session_id:
            await _save_chat_messages(db, request.session_id, request.query, denial)
        return QueryResponse(
            query=request.query,
            answer=denial,
            citations=[],
            access_decision="denied",
            chunks_retrieved=0,
            session_id=request.session_id,
        )

    # 4. Generate response — wrapped so an LLM failure still writes an audit row
    retrieved_ids = [str(c.chunk_id) for c in chunks]
    try:
        answer = await llm_client.generate(
            request.query,
            [c.chunk_text for c in chunks],
        )
        access_decision = "allowed"
    except Exception:
        # LLM is unavailable or crashed — log the error, return partial response
        fallback = "The language model is currently unavailable. Retrieved documents are cited below."
        await write_audit_log(
            db,
            user_id=current_user.id,
            query=request.query,
            retrieved_doc_ids=retrieved_ids,
            response_time_ms=int(time.monotonic() * 1000) - start_ms,
            access_decision="error",
        )
        if request.session_id:
            await _save_chat_messages(db, request.session_id, request.query, fallback)
        return QueryResponse(
            query=request.query,
            answer=fallback,
            citations=_build_citations(chunks),
            access_decision="allowed",
            chunks_retrieved=len(chunks),
            session_id=request.session_id,
        )

    # 5. Save chat history
    if request.session_id:
        await _save_chat_messages(db, request.session_id, request.query, answer)

    # 6. Write audit log
    await write_audit_log(
        db,
        user_id=current_user.id,
        query=request.query,
        retrieved_doc_ids=retrieved_ids,
        response_time_ms=int(time.monotonic() * 1000) - start_ms,
        access_decision=access_decision,
    )

    # 7. Return with citations
    return QueryResponse(
        query=request.query,
        answer=answer,
        citations=_build_citations(chunks),
        access_decision=access_decision,
        chunks_retrieved=len(chunks),
        session_id=request.session_id,
    )
