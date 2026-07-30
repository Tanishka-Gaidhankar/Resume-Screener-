from __future__ import annotations

from pathlib import Path
from typing import Optional


def _extract_pdf(path: Path) -> str:
    try:
        from unstructured.partition.pdf import partition_pdf  # type: ignore
    except Exception:
        partition_pdf = None

    if partition_pdf is not None:
        try:
            elements = partition_pdf(filename=str(path))
            text = "\n".join(element.text for element in elements if getattr(element, "text", "").strip())
            if text.strip():
                return text.strip()
        except Exception:
            pass

    import pdfplumber  # type: ignore

    with pdfplumber.open(str(path)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages).strip()


def _extract_docx(path: Path) -> str:
    import docx  # type: ignore

    document = docx.Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text).strip()


def extract_text(file_path: str | Path) -> str:
    """Extract text from a resume file. Supports plain text, PDF, and DOCX with robust fallbacks."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore").strip()

    if suffix == ".pdf":
        return _extract_pdf(path)

    if suffix == ".docx":
        return _extract_docx(path)

    # Fallback for temp files or missing extensions
    try:
        return _extract_pdf(path)
    except Exception:
        pass

    try:
        return _extract_docx(path)
    except Exception:
        pass

    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception as exc:
        raise ValueError(f"Unsupported or unreadable file type: {path}") from exc

