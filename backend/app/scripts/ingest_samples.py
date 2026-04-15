"""Ingest all sample enterprise documents into the vector store.

Reads docs/sample/manifest.json, ingests each document, then creates
the ivfflat index if enough chunks are present.

Run:
    docker compose exec backend python -m app.scripts.ingest_samples
    # or locally (from backend/):
    python -m app.scripts.ingest_samples
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

from app.core.database import AsyncSessionLocal
from app.ingestion.pipeline import ingest_document
from app.ingestion.schemas import DocType, DocumentManifest, SecurityLevel
from app.retrieval.index import create_ivfflat_index, get_chunk_count

# Manifest path relative to project root
_MANIFEST_PATH = Path(__file__).resolve().parents[4] / "docs" / "sample" / "manifest.json"
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _load_manifests() -> list[DocumentManifest]:
    with open(_MANIFEST_PATH, encoding="utf-8") as f:
        entries = json.load(f)

    manifests = []
    for e in entries:
        file_path = str(_PROJECT_ROOT / e["file_path"])
        if not Path(file_path).exists():
            logger.warning("File not found, skipping: %s", file_path)
            continue
        manifests.append(
            DocumentManifest(
                file_path=file_path,
                title=e["title"],
                department=e["department"],
                role_required=e["role_required"],
                doc_type=DocType(e["doc_type"]),
                security_level=SecurityLevel(e["security_level"]),
                classification=e["classification"],
                version=e.get("version", "v1"),
                tags=e.get("tags", []),
            )
        )
    return manifests


async def main(force_reingest: bool = False) -> None:
    manifests = _load_manifests()
    logger.info("Found %d documents in manifest", len(manifests))

    results = []
    async with AsyncSessionLocal() as db:
        for manifest in manifests:
            logger.info("Ingesting: %s", manifest.title)
            result = await ingest_document(db, manifest, force_reingest=force_reingest)
            results.append(result)

        # ── Summary ────────────────────────────────────────────────────────
        ingested = [r for r in results if not r.skipped]
        skipped = [r for r in results if r.skipped]
        total_chunks = sum(r.chunks_created for r in ingested)

        logger.info("─" * 50)
        logger.info("Ingested : %d documents / %d chunks", len(ingested), total_chunks)
        if skipped:
            logger.info("Skipped  : %d documents", len(skipped))
            for s in skipped:
                logger.info("  • %s — %s", s.title, s.skip_reason)

        # ── ivfflat index ──────────────────────────────────────────────────
        count = await get_chunk_count(db)
        logger.info("Total embedded chunks in DB: %d", count)
        index_result = await create_ivfflat_index(db, chunk_count=count)
        logger.info("Index status: %s", index_result)

    logger.info("Done.")


if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        logger.info("--force flag detected: re-ingesting all documents")
    asyncio.run(main(force_reingest=force))
