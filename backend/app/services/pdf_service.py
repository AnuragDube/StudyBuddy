"""Syllabus text extraction from uploaded PDF / TXT files using PyMuPDF.

Every failure mode (empty upload, wrong type, corrupt or encrypted PDF,
image-only PDF without a text layer, oversize file) raises
:class:`SyllabusExtractionError`, which the API layer maps to HTTP 400.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath

import pymupdf

from app.core.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".text"}
MIN_TEXT_CHARS = 20
_PDF_MAGIC = b"%PDF"


class SyllabusExtractionError(ValueError):
    """Raised when a syllabus file cannot be turned into usable text."""


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    source_type: str  # "pdf" | "text"
    page_count: int
    char_count: int
    filename: str


def clean_text(raw: str) -> str:
    """Normalise whitespace and remove common PDF artefacts."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = text.replace("\x00", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)           # de-hyphenate line breaks
    text = re.sub(r"(?m)^\s*(page\s*)?\d+\s*(of\s*\d+)?\s*$", "", text, flags=re.I)  # page numbers
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf(content: bytes) -> tuple[str, int]:
    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:  # pymupdf raises FileDataError / RuntimeError variants
        raise SyllabusExtractionError("The PDF file is corrupt or unreadable.") from exc

    with doc:
        if doc.needs_pass:
            raise SyllabusExtractionError("The PDF is password-protected. Please upload an unlocked copy.")
        if doc.page_count == 0:
            raise SyllabusExtractionError("The PDF has no pages.")
        try:
            pages = [page.get_text("text", sort=True) for page in doc]
        except Exception as exc:
            raise SyllabusExtractionError("Failed to read text from the PDF.") from exc
        return "\n\n".join(pages), doc.page_count


def _decode_text(content: bytes) -> str:
    if b"\x00" in content[:4096]:
        raise SyllabusExtractionError("The text file appears to be binary, not plain text.")
    for encoding in ("utf-8-sig", "utf-16") if content[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig",):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("cp1252", errors="replace")


def extract_syllabus_text(filename: str, content: bytes, max_bytes: int | None = None) -> ExtractionResult:
    """Extract clean syllabus text from raw upload bytes."""
    name = filename or "upload"
    if not content:
        raise SyllabusExtractionError("The uploaded file is empty.")
    if max_bytes is not None and len(content) > max_bytes:
        raise SyllabusExtractionError(
            f"The file is too large ({len(content) / 1_048_576:.1f} MB). "
            f"Maximum allowed is {max_bytes / 1_048_576:.0f} MB."
        )

    ext = PurePath(name).suffix.lower()
    is_pdf = content[:1024].lstrip().startswith(_PDF_MAGIC)

    if ext == ".pdf" or is_pdf:
        if ext == ".pdf" and not is_pdf:
            raise SyllabusExtractionError("The file has a .pdf extension but is not a valid PDF.")
        raw, pages, source = *_extract_pdf(content), "pdf"
    elif ext in SUPPORTED_EXTENSIONS:
        raw, pages, source = _decode_text(content), 1, "text"
    else:
        raise SyllabusExtractionError(
            f"Unsupported file type '{ext or 'unknown'}'. Upload a PDF or TXT syllabus."
        )

    text = clean_text(raw)
    if len(text) < MIN_TEXT_CHARS:
        hint = (
            " This PDF may be scanned/image-only; OCR is not supported. Paste the text instead."
            if source == "pdf"
            else ""
        )
        raise SyllabusExtractionError(f"No readable syllabus text was found in the file.{hint}")

    logger.info("Extracted syllabus text", extra={"file": name, "pages": pages, "chars": len(text)})
    return ExtractionResult(text=text, source_type=source, page_count=pages, char_count=len(text), filename=name)
