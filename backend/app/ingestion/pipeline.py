"""Main ingestion pipeline.

Flow per document:
  1. Extract text  (parser.py)
  2. Chunk text    (chunker.py) — strategy selected by file extension
  3. Embed chunks  (embedder.py) — batched, 384-dim
  4. Upsert to DB  (SQLAlchemy async) — idempotent: delete existing chunks first

Usage:
    from app.ingestion.pipeline import ingest_document
    result = await ingest_document(db, manifest=DocumentManifest(...))

Or via CLI script:
    python -m app.scripts.ingest_samples
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.chunker import chunk_document
from app.ingestion.embedder import embed_texts
from app.ingestion.parser import extract_text
from app.ingestion.schemas import DocumentManifest, EmbeddedChunk, IngestResult
from app.models.chunk import DocumentChunk
from app.models.document import Document

logger = logging.getLogger(__name__)


async def ingest_document(
    db: AsyncSession,
    manifest: DocumentManifest,
    *,
    force_reingest: bool = False,
) -> IngestResult:
    """Ingest a single document from a DocumentManifest.

    Idempotent: if a Document row with the same title + version already exists,
    the function skips ingestion unless force_reingest=True.
    On force_reingest, existing chunks for that document are deleted and recreated.
    """
    source_file = Path(manifest.file_path).name

    # ── 1. Check for existing document ───────────────────────────────────────
    existing = await db.execute(
        select(Document).where(
            Document.title == manifest.title,
            Document.version == manifest.version,
        )
    )
    doc = existing.scalar_one_or_none()

    if doc is not None and not force_reingest:
        logger.info("Skipping '%s' v%s — already ingested", manifest.title, manifest.version)
        return IngestResult(
            document_id=str(doc.id),
            title=manifest.title,
            source_file=source_file,
            chunks_created=0,
            department=manifest.department,
            role_required=manifest.role_required,
            skipped=True,
            skip_reason="already ingested (use force_reingest=True to overwrite)",
        )

    # ── 2. Extract text ───────────────────────────────────────────────────────
    logger.info("Extracting text from %s", manifest.file_path)
    raw_text = extract_text(manifest.file_path)

    # ── 3. Chunk ──────────────────────────────────────────────────────────────
    raw_chunks = chunk_document(raw_text, manifest.title, manifest.file_path)
    logger.info("'%s' → %d chunks", manifest.title, len(raw_chunks))

    if not raw_chunks:
        return IngestResult(
            document_id="",
            title=manifest.title,
            source_file=source_file,
            chunks_created=0,
            department=manifest.department,
            role_required=manifest.role_required,
            skipped=True,
            skip_reason="no text extracted from document",
        )

    # ── 4. Embed ──────────────────────────────────────────────────────────────
    texts = [c.text for c in raw_chunks]
    embeddings = embed_texts(texts)

    embedded_chunks = [
        EmbeddedChunk(
            text=rc.text,
            section_header=rc.section_header,
            chunk_index=rc.chunk_index,
            embedding=emb,
            metadata={
                "section_header": rc.section_header,
                "department": manifest.department,
                "role_required": manifest.role_required,
                "doc_type": manifest.doc_type.value,
                "security_level": manifest.security_level.value,
                "source_file": source_file,
                "chunk_index": rc.chunk_index,
                "tags": manifest.tags,
            },
        )
        for rc, emb in zip(raw_chunks, embeddings)
    ]

    # ── 5. Upsert to DB ───────────────────────────────────────────────────────
    if doc is None:
        doc = Document(
            id=uuid.uuid4(),
            title=manifest.title,
            source_type=Path(manifest.file_path).suffix.lstrip(".").lower(),
            department=manifest.department,
            classification=manifest.classification,
            version=manifest.version,
        )
        db.add(doc)
        await db.flush()  # get doc.id before inserting chunks
    else:
        # force_reingest — wipe existing chunks
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        )
        await db.flush()

    # Bulk insert chunks
    chunk_rows = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_text=ec.text,
            embedding=ec.embedding,
            chunk_index=ec.chunk_index,
            role_required=manifest.role_required,
            metadata=ec.metadata,
        )
        for ec in embedded_chunks
    ]
    db.add_all(chunk_rows)
    await db.commit()

    logger.info(
        "Ingested '%s' → %d chunks [dept=%s, role=%s]",
        manifest.title,
        len(chunk_rows),
        manifest.department,
        manifest.role_required,
    )

    return IngestResult(
        document_id=str(doc.id),
        title=manifest.title,
        source_file=source_file,
        chunks_created=len(chunk_rows),
        department=manifest.department,
        role_required=manifest.role_required,
    )
