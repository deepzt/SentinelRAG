"""Data transfer objects for the ingestion pipeline.

These are internal DTOs — not exposed via API.
"""

from dataclasses import dataclass, field
from enum import Enum


class SourceType(str, Enum):
    PDF = "pdf"
    MARKDOWN = "markdown"


class DocType(str, Enum):
    RUNBOOK = "runbook"
    POLICY = "policy"
    SOP = "sop"
    CHECKLIST = "checklist"
    TEMPLATE = "template"
    GUIDE = "guide"


class SecurityLevel(str, Enum):
    L1 = "L1"  # public-facing
    L2 = "L2"  # internal only
    L3 = "L3"  # confidential / restricted


@dataclass
class DocumentManifest:
    """Per-document ingestion metadata — provided at ingest time."""

    file_path: str
    title: str
    department: str          # "engineering" | "hr" | "legal"
    role_required: str       # "engineer" | "hr" | "manager"
    doc_type: DocType
    security_level: SecurityLevel
    classification: str      # "internal" | "confidential" | "public"
    version: str = "v1"
    tags: list[str] = field(default_factory=list)


@dataclass
class RawChunk:
    """A single text chunk before embedding."""

    text: str
    section_header: str
    chunk_index: int


@dataclass
class EmbeddedChunk:
    """A chunk with its embedding vector, ready for DB insert."""

    text: str
    section_header: str
    chunk_index: int
    embedding: list[float]  # length must be EMBEDDING_DIMENSION (384)
    metadata: dict           # full JSONB metadata blob


@dataclass
class IngestResult:
    """Summary returned after ingesting a document."""

    document_id: str
    title: str
    source_file: str
    chunks_created: int
    department: str
    role_required: str
    skipped: bool = False
    skip_reason: str = ""
