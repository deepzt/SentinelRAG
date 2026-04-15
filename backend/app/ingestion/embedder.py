"""Batch embedding using sentence-transformers.

Model is loaded once at module level and reused across calls.
Dimension is ALWAYS 384 (all-MiniLM-L6-v2) — do NOT change without
updating document_chunks.embedding VECTOR(384) and re-embedding all data.
"""

from __future__ import annotations

import logging

from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None

EMBED_BATCH_SIZE = 32


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        dim = _model.get_sentence_embedding_dimension()
        if dim != settings.EMBEDDING_DIMENSION:
            raise RuntimeError(
                f"Model dimension mismatch: got {dim}, expected {settings.EMBEDDING_DIMENSION}. "
                "If you changed EMBEDDING_MODEL, you must drop and re-create all embeddings."
            )
        logger.info("Embedding model loaded (%d-dim)", dim)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in batches.

    Returns a list of 384-dim float vectors in the same order as input.
    normalize_embeddings=True ensures cosine similarity = dot product,
    which pgvector's <=> operator exploits directly.
    """
    model = get_model()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        vectors = model.encode(
            batch,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=EMBED_BATCH_SIZE,
        )
        all_embeddings.extend(vectors.tolist())

    return all_embeddings
