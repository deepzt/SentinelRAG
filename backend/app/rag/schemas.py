import uuid
from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=20)
    session_id: uuid.UUID | None = Field(default=None)


class CitationItem(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    section_header: str
    department: str
    doc_type: str
    score: float


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: list[CitationItem]
    access_decision: str  # "allowed" | "denied"
    chunks_retrieved: int
    session_id: uuid.UUID | None = None


class RetrievedChunk(BaseModel):
    """Internal DTO — not exposed to API consumers."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_text: str
    title: str
    metadata: dict[str, Any]
    score: float
