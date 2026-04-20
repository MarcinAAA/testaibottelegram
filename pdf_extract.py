"""Extract plain text from PDF bytes (best-effort)."""

from io import BytesIO

from pypdf import PdfReader


def extract_pdf_text(data: bytes, max_chars: int = 80_000) -> str:
    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    full = "\n".join(parts).strip()
    if not full:
        return ""
    if len(full) > max_chars:
        return full[:max_chars] + "\n\n[... truncated for API size ...]"
    return full
