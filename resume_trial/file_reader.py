from __future__ import annotations

from pathlib import Path
from typing import Optional


def extract_text(file_path: str | Path) -> str:
    """Extract text from a resume file. Supports plain text, PDF, and DOCX.

    This is a lightweight trial implementation that uses plain text directly
    and can be extended to pdfplumber/python-docx in a full app.
    """
    path = Path(file_path)
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8")

    if path.suffix.lower() == ".pdf":
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

        try:
            import pdfplumber  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pdfplumber is required for PDF extraction") from exc

        with pdfplumber.open(str(path)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(pages).strip()

    if path.suffix.lower() == ".docx":
        try:
            import docx  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("python-docx is required for DOCX extraction") from exc

        document = docx.Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text).strip()

    raise ValueError(f"Unsupported file type: {path.suffix}")
