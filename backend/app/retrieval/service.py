"""Enhanced RBAC-filtered pgvector retrieval.

Owned by RAG Engineer. This module is the canonical retrieval implementation.
rag/retrieval.py delegates here.

Enhancements over the initial BackendDev stub:
  - Score threshold filtering (MIN_SCORE) — rejects low-quality matches
  - Per-document chunk cap (MAX_CHUNKS_PER_DOC) — prevents one doc from
    dominating results when it has many matching chunks
  - Explicit pgvector operator hint (<=> cosine distance) for clarity
  - Correct vector casting compatible with asyncpg
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.schemas import RetrievedChunk

MIN_SCORE: float = 0.25       # Chunks below this cosine similarity are discarded
MAX_CHUNKS_PER_DOC: int = 2   # Max chunks returned per unique document


# RBAC via access_policies JOIN (single source of truth):
# The JOIN enforces: user's role must have a policy permitting the chunk's
# department AND the document's classification. No hardcoded role checks.
# dc.role_required is NOT used as a filter here — it records the minimum role
# at ingest time but access decisions are owned by the access_policies table.
# The inner CTE scores all permitted chunks; the outer SELECT deduplicates per doc.

_RBAC_SEARCH_SQL = text(
    """
    WITH ranked AS (
        SELECT
            dc.id                                                          AS chunk_id,
            dc.document_id,
            dc.chunk_text,
            d.title,
            dc.metadata,
            1 - (dc.embedding <=> :query_embedding ::vector)              AS score,
            ROW_NUMBER() OVER (
                PARTITION BY dc.document_id
                ORDER BY dc.embedding <=> :query_embedding ::vector
            ) AS rn
        FROM document_chunks dc
        JOIN documents d
            ON d.id = dc.document_id
        JOIN access_policies ap
            ON ap.role       = :user_role
           AND ap.department = (dc.metadata ->> 'department')
           AND d.classification = ANY(
               string_to_array(ap.allowed_classification, ',')
           )
        WHERE dc.embedding IS NOT NULL
    )
    SELECT chunk_id, document_id, chunk_text, title, metadata, score
    FROM   ranked
    WHERE  rn     <= :max_per_doc
      AND  score  >= :min_score
    ORDER BY score DESC
    LIMIT :top_k
    """
)


async def rbac_vector_search(
    db: AsyncSession,
    *,
    query_embedding: list[float],
    user_role: str,
    top_k: int = 4,
    min_score: float = MIN_SCORE,
    max_chunks_per_doc: int = MAX_CHUNKS_PER_DOC,
) -> list[RetrievedChunk]:
    """Execute RBAC-filtered pgvector similarity search.

    Returns chunks the user's role is permitted to see, ranked by cosine
    similarity. Low-scoring results and over-represented documents are pruned.
    """
    # asyncpg requires the embedding as a string; PostgreSQL's ::vector cast
    # accepts '[0.1, 0.2, ...]' string syntax. Passing a raw Python list fails
    # without the pgvector asyncpg codec registered on the connection.
    result = await db.execute(
        _RBAC_SEARCH_SQL,
        {
            "query_embedding": str(query_embedding),
            "user_role": user_role,
            "top_k": top_k,
            "min_score": min_score,
            "max_per_doc": max_chunks_per_doc,
        },
    )
    rows = result.mappings().all()

    return [
        RetrievedChunk(
            chunk_id=uuid.UUID(str(row["chunk_id"])),
            document_id=uuid.UUID(str(row["document_id"])),
            chunk_text=row["chunk_text"],
            title=row["title"],
            metadata=dict(row["metadata"]) if row["metadata"] else {},
            score=float(row["score"]),
        )
        for row in rows
    ]
