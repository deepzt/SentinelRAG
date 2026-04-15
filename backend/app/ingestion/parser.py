"""Document text extraction.

Handles two source types:
  - Markdown (.md)  — read as UTF-8 text
  - PDF (.pdf)      — extract via pdfplumber, join pages with double newline

Output is always a plain text string ready for chunking.
"""

import os
from pathlib import Path


def extract_text(file_path: str) -> str:
    """Extract plain text from a Markdown or PDF file.

    Raises ValueError for unsupported extensions.
    Raises FileNotFoundError if the path does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    ext = path.suffix.lower()
    if ext == ".md":
        return _extract_markdown(path)
    elif ext == ".pdf":
        return _extract_pdf(path)
    else:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: .md, .pdf")


def _extract_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError as e:
        raise ImportError(
            "pdfplumber is required for PDF ingestion. "
            "Install it: pip install pdfplumber"
        ) from e

    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())

    if not pages:
        raise ValueError(f"No text could be extracted from PDF: {path.name}")

    return "\n\n".join(pages)
