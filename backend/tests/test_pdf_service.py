"""Unit tests for the PyMuPDF syllabus extraction service."""

import pymupdf
import pytest

from app.services.pdf_service import SyllabusExtractionError, clean_text, extract_syllabus_text

SYLLABUS = (
    "Unit 1: Introduction to Operating Systems and system calls.\n"
    "Unit 2: Process scheduling algorithms (FCFS, SJF, Round Robin).\n"
    "Unit 3: Memory management, paging and segmentation."
)


def make_pdf(pages: list[str], password: str | None = None) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=11)
    kwargs = {}
    if password:
        kwargs = {"encryption": pymupdf.PDF_ENCRYPT_AES_256, "owner_pw": password, "user_pw": password}
    data = doc.tobytes(**kwargs)
    doc.close()
    return data


def test_extracts_text_from_multi_page_pdf():
    result = extract_syllabus_text("os.pdf", make_pdf([SYLLABUS, "Unit 4: File systems and I/O."]))
    assert result.source_type == "pdf"
    assert result.page_count == 2
    assert "Process scheduling" in result.text
    assert "File systems" in result.text
    assert result.char_count == len(result.text)


def test_detects_pdf_by_magic_bytes_even_without_extension():
    result = extract_syllabus_text("syllabus", make_pdf([SYLLABUS]))
    assert result.source_type == "pdf"


def test_extracts_utf8_text_file_with_bom():
    result = extract_syllabus_text("os.txt", ("\ufeff" + SYLLABUS).encode("utf-8"))
    assert result.source_type == "text"
    assert result.text.startswith("Unit 1")


def test_falls_back_to_cp1252_for_legacy_text():
    result = extract_syllabus_text("os.txt", ("Résumé of " + SYLLABUS).encode("cp1252"))
    assert "Résumé" in result.text


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("empty.pdf", b"", "empty"),
        ("broken.pdf", b"%PDF-1.7\nthis is not really a pdf", "corrupt"),
        ("fake.pdf", b"just some text pretending to be a pdf", "not a valid PDF"),
        ("image.png", b"\x89PNG\r\n\x1a\n....", "Unsupported file type"),
        ("binary.txt", b"abc\x00\x01\x02" * 10, "binary"),
        ("short.txt", b"Too short", "No readable"),
    ],
)
def test_invalid_inputs_raise_clear_errors(filename, content, message):
    with pytest.raises(SyllabusExtractionError, match=message):
        extract_syllabus_text(filename, content)


def test_blank_pdf_reports_possible_scan():
    with pytest.raises(SyllabusExtractionError, match="scanned"):
        extract_syllabus_text("scan.pdf", make_pdf(["", ""]))


def test_password_protected_pdf_rejected():
    with pytest.raises(SyllabusExtractionError, match="password"):
        extract_syllabus_text("locked.pdf", make_pdf([SYLLABUS], password="secret"))


def test_oversize_file_rejected():
    with pytest.raises(SyllabusExtractionError, match="too large"):
        extract_syllabus_text("big.txt", b"a" * 2048, max_bytes=1024)


def test_clean_text_removes_artifacts():
    raw = "Intro-\nduction\r\n\r\n\r\n\r\nPage 3 of 10\n  Memory    management  \n12\n"
    assert clean_text(raw) == "Introduction\n\nMemory management"
