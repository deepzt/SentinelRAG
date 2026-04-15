"""RBAC-filtered pgvector retrieval.

Owned by BackendDev (rag/ module).
RAG Engineer will enhance chunking strategy and query tuning in retrieval/.

The RBAC filter is applied inside the SQL query — never post-retrieval in Python.
Two-layer filter:
  1. document_chunks.role_required = :user_role   (fast indexed column check)
  2. JOIN access_policies to verify the role has access to the doc's department
     and classification (policy-table RBAC — mirrors IAM/OpenFGA patterns)
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.schemas import RetrievedChunk

_RBAC_SEARCH_SQL = text(
    """
    SELECT
        dc.id            AS chunk_id,
        dc.document_id,
        dc.chunk_text,
        d.title,
        dc.metadata,
        1 - (dc.embedding <=> CAST(:query_embedding AS vector)) AS score
    FROM document_chunks dc
    JOIN documents d
        ON d.id = dc.document_id
    JOIN access_policies ap
        ON ap.role      = :user_role
        AND ap.department = (dc.metadata->>'department')
        AND (
            ap.allowed_classification LIKE '%' || d.classification || '%'
        )
    WHERE dc.role_required = :user_role
      AND dc.embedding IS NOT NULL
    ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
    LIMIT :top_k
    """
)


async def rbac_vector_search(
    db: AsyncSession,
    *,
    query_embedding: list[float],
    user_role: str,
    top_k: int = 4,
) -> list[RetrievedChunk]:
    """Execute RBAC-filtered pgvector similarity search.

    Returns only chunks the user's role is permitted to see, ranked by
    cosine similarity to the query embedding.
    """
    result = await db.execute(
        _RBAC_SEARCH_SQL,
        {
            "query_embedding": str(query_embedding),
            "user_role": user_role,
            "top_k": top_k,
        },
    )
    rows = result.mappings().all()

    return [
        RetrievedChunk(
            chunk_id=uuid.UUID(str(row["chunk_id"])),
            document_id=uuid.UUID(str(row["document_id"])),
            chunk_text=row["chunk_text"],
            title=row["title"],
            metadata=row["metadata"] or {},
            score=float(row["score"]),
        )
        for row in rows
    ]
