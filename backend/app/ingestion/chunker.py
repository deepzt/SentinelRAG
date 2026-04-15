"""Document chunking — canonical strategy.

Markdown files:
  1. Split on ## / ### headers — each section is a candidate chunk.
  2. Sections > CHUNK_SIZE are recursively split using the separator hierarchy.

PDF files:
  1. Apply recursive character splitting directly.

Parameters (canonical — do not change without Architect approval):
  CHUNK_SIZE = 1500 characters (~400 tokens)
  OVERLAP    = 200 characters (~60 tokens)
  SEPARATORS = ["\n\n", "\n", ". ", " "]
"""

import re
from pathlib import Path

from app.ingestion.schemas import RawChunk

CHUNK_SIZE = 1500
OVERLAP = 200
SEPARATORS = ["\n\n", "\n", ". ", " "]

# Matches ## Header or ### Header at start of line
_HEADER_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)


# ── Low-level split ───────────────────────────────────────────────────────────

def _split_at_boundary(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Split a block of text into chunks ≤ chunk_size.

    Tries to break at natural boundaries (paragraph, line, sentence, word)
    and prepends an overlap window from the previous chunk so context
    is not lost at boundaries.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    results: list[str] = []
    remaining = text

    while len(remaining) > chunk_size:
        window = remaining[:chunk_size]
        cut = chunk_size

        # Find the best natural break point in the window
        for sep in SEPARATORS:
            pos = window.rfind(sep)
            # Only accept if it cuts after the first third (avoid micro-chunks)
            if pos > chunk_size // 3:
                cut = pos + len(sep)
                break

        chunk = remaining[:cut].strip()
        if chunk:
            results.append(chunk)

        # Advance with overlap — new chunk begins overlap chars before the cut
        overlap_start = max(0, cut - overlap)
        remaining = remaining[overlap_start:].strip()

        # Safety guard: if nothing was consumed, force advance
        if overlap_start == 0:
            remaining = remaining[cut:].strip()

    if remaining:
        results.append(remaining)

    return results


# ── Markdown chunker ──────────────────────────────────────────────────────────

def chunk_markdown(text: str, doc_title: str) -> list[RawChunk]:
    """Split Markdown by ## / ### headers, then recursively split large sections.

    Sections that fit within CHUNK_SIZE are kept whole (one chunk per section).
    Longer sections are split with _split_at_boundary, preserving the header
    as section_header metadata on every sub-chunk.
    """
    header_matches = list(_HEADER_RE.finditer(text))

    # No headers — treat the whole document as a single section
    if not header_matches:
        splits = _split_at_boundary(text)
        return [RawChunk(t, doc_title, i) for i, t in enumerate(splits)]

    results: list[RawChunk] = []
    chunk_idx = 0

    # Preamble before the first header
    preamble = text[: header_matches[0].start()].strip()
    if preamble:
        for sub in _split_at_boundary(preamble):
            results.append(RawChunk(sub, doc_title, chunk_idx))
            chunk_idx += 1

    # Each header → section
    for i, match in enumerate(header_matches):
        header_text = match.group(2).strip()
        section_start = match.start()
        section_end = header_matches[i + 1].start() if i + 1 < len(header_matches) else len(text)
        section = text[section_start:section_end].strip()

        if len(section) <= CHUNK_SIZE:
            if section:
                results.append(RawChunk(section, header_text, chunk_idx))
                chunk_idx += 1
        else:
            for sub in _split_at_boundary(section):
                results.append(RawChunk(sub, header_text, chunk_idx))
                chunk_idx += 1

    return results


# ── PDF chunker ───────────────────────────────────────────────────────────────

def chunk_pdf(text: str, doc_title: str) -> list[RawChunk]:
    """Recursively split PDF text (no header structure assumed)."""
    splits = _split_at_boundary(text)
    return [RawChunk(t, doc_title, i) for i, t in enumerate(splits)]


# ── Router ────────────────────────────────────────────────────────────────────

def chunk_document(text: str, doc_title: str, source_file: str) -> list[RawChunk]:
    """Route to the correct chunking strategy based on file extension."""
    ext = Path(source_file).suffix.lower()
    if ext == ".pdf":
        return chunk_pdf(text, doc_title)
    else:
        return chunk_markdown(text, doc_title)
