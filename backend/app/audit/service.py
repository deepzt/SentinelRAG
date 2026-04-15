import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def write_audit_log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    query: str,
    retrieved_doc_ids: list[str],
    response_time_ms: int | None,
    access_decision: str,  # "allowed" | "denied" | "error"
) -> AuditLog:
    """Append a row to audit_logs.

    This function is the ONLY way audit logs are written.
    Called exclusively by the RAG service — never from route handlers.
    The table is append-only: no update or delete operations exist.
    """
    log = AuditLog(
        user_id=user_id,
        query=query,
        retrieved_doc_ids=retrieved_doc_ids,
        response_time_ms=response_time_ms,
        access_decision=access_decision,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log
