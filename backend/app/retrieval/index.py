"""pgvector index management.

IVFFlat index creation should run AFTER bulk ingestion — not before.
The index requires data to compute centroids. Creating it on an empty table
produces a useless index.

Usage (via ingest_samples.py or manually):
    from app.retrieval.index import create_ivfflat_index, get_chunk_count
    count = await get_chunk_count(db)
    await create_ivfflat_index(db, chunk_count=count)

ivfflat tuning guide:
  - lists = sqrt(n_rows) is a good starting point
  - Minimum: 100 lists (below this, flat scan is comparable)
  - At query time: set ivfflat.probes = sqrt(lists) for recall / speed tradeoff
  - For production (>100k rows), consider HNSW instead of ivfflat
"""

import logging
import math

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

INDEX_NAME = "idx_chunks_embedding_ivfflat"
MIN_ROWS_FOR_INDEX = 50   # Don't bother indexing tiny datasets
MIN_LISTS = 100


async def get_chunk_count(db: AsyncSession) -> int:
    """Return the number of rows in document_chunks that have an embedding."""
    result = await db.execute(
        text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
    )
    return result.scalar_one()


async def index_exists(db: AsyncSession) -> bool:
    result = await db.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename = 'document_chunks' AND indexname = :name"
        ),
        {"name": INDEX_NAME},
    )
    return result.scalar_one_or_none() is not None


async def drop_ivfflat_index(db: AsyncSession) -> None:
    """Drop the ivfflat index. Call before re-ingesting the full corpus."""
    await db.execute(
        text(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
    )
    await db.commit()
    logger.info("Dropped ivfflat index %s", INDEX_NAME)


async def create_ivfflat_index(
    db: AsyncSession,
    chunk_count: int | None = None,
    force_recreate: bool = False,
) -> dict:
    """Create an IVFFlat cosine-distance index on document_chunks.embedding.

    Args:
        chunk_count: pre-fetched row count (re-queried if None)
        force_recreate: drop existing index and rebuild

    Returns a status dict with lists, chunk_count, action taken.
    """
    if chunk_count is None:
        chunk_count = await get_chunk_count(db)

    if chunk_count < MIN_ROWS_FOR_INDEX:
        msg = (
            f"Only {chunk_count} embedded chunks — skipping ivfflat index "
            f"(minimum {MIN_ROWS_FOR_INDEX}). Index will be created after more documents are ingested."
        )
        logger.warning(msg)
        return {"action": "skipped", "reason": msg, "chunk_count": chunk_count}

    if await index_exists(db):
        if not force_recreate:
            logger.info("Index %s already exists — skipping", INDEX_NAME)
            return {"action": "exists", "chunk_count": chunk_count}
        await drop_ivfflat_index(db)

    # lists = sqrt(n) is the standard recommendation
    lists = max(MIN_LISTS, int(math.sqrt(chunk_count)))
    logger.info(
        "Creating ivfflat index on %d chunks (lists=%d)…", chunk_count, lists
    )

    # CONCURRENTLY allows reads during index build (no table lock)
    await db.execute(
        text(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME}
            ON document_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = {lists})
            """
        )
    )
    await db.commit()

    logger.info("ivfflat index created: %s (lists=%d)", INDEX_NAME, lists)
    return {"action": "created", "lists": lists, "chunk_count": chunk_count}


async def set_query_probes(db: AsyncSession, probes: int | None = None) -> None:
    """Set ivfflat.probes for the current connection.

    Higher probes = better recall, slower query.
    Default: sqrt(lists). Call this at the start of a retrieval session.
    """
    if probes is None:
        # Fetch lists from pg_index to compute default
        result = await db.execute(
            text(
                "SELECT reloptions FROM pg_class "
                "WHERE relname = :name",
            ),
            {"name": INDEX_NAME},
        )
        row = result.scalar_one_or_none()
        if row and row:
            for opt in row:
                if opt.startswith("lists="):
                    lists = int(opt.split("=")[1])
                    probes = max(1, int(math.sqrt(lists)))
                    break
        probes = probes or 10

    await db.execute(text(f"SET ivfflat.probes = {probes}"))
