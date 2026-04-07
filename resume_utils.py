from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Union

from docx import Document
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


def _read_text_file(data: bytes) -> str:
    return data.decode("utf-8", errors="ignore")


def extract_resume_text(uploaded_file) -> str:
    """Extract plain text from a resume uploaded in Streamlit."""
    if uploaded_file is None:
        return ""

    filename = getattr(uploaded_file, "name", "") or ""
    ext = Path(filename).suffix.lower()
    raw = uploaded_file.getvalue()

    if ext in {".txt", ".md"}:
        return _read_text_file(raw).strip()

    if ext == ".pdf":
        reader = PdfReader(BytesIO(raw))
        parts = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                parts.append(text)
        return "\n".join(parts).strip()

    if ext == ".docx":
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(suffix=".docx", delete=True) as tmp:
            tmp.write(raw)
            tmp.flush()
            doc = Document(tmp.name)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()

    # Fallback: try utf-8 text.
    return _read_text_file(raw).strip()
