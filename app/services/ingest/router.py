from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, is_zipfile

from app.schemas import DocumentContent
from app.services.ingest.excel import CSV_SUFFIXES, EXCEL_SUFFIXES, ingest_spreadsheet
from app.services.ingest.image import IMAGE_SUFFIXES, ingest_image
from app.services.ingest.pdf import ingest_pdf
from app.services.ingest.word import ingest_docx

PDF_SUFFIXES = {".pdf"}
WORD_SUFFIXES = {".docx"}
SUPPORTED_SUFFIXES = EXCEL_SUFFIXES | CSV_SUFFIXES | PDF_SUFFIXES | WORD_SUFFIXES | IMAGE_SUFFIXES


class UnsupportedDocumentError(ValueError):
    pass


def guess_filename(data: bytes) -> str:
    if data.startswith(b"%PDF"):
        return "document.pdf"
    if data.startswith(b"\x89PNG"):
        return "document.png"
    if data.startswith(b"\xff\xd8\xff"):
        return "document.jpg"
    if data.startswith(b"BM"):
        return "document.bmp"
    if data[:4] in {b"II*\x00", b"MM\x00*"}:
        return "document.tif"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "document.webp"
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        return "document.xls"
    if is_zipfile(BytesIO(data)):
        with ZipFile(BytesIO(data)) as archive:
            names = archive.namelist()
        if any(name.startswith("word/") for name in names):
            return "document.docx"
        if any(name.startswith("xl/") for name in names):
            return "document.xlsx"
        return "document.xlsx"
    sample = data[:1024]
    if b"," in sample and b"\n" in sample and not data.startswith(b"{"):
        return "document.csv"
    raise UnsupportedDocumentError(
        "Unsupported file type. Use pdf, xlsx, xls, csv, docx, jpg, png, or webp."
    )


def ingest_file(data: bytes, filename: str) -> DocumentContent:
    suffix = Path(filename).suffix.lower()
    if suffix in EXCEL_SUFFIXES or suffix in CSV_SUFFIXES:
        return ingest_spreadsheet(data, filename, suffix)
    if suffix in PDF_SUFFIXES:
        return ingest_pdf(data, filename)
    if suffix in WORD_SUFFIXES:
        return ingest_docx(data, filename)
    if suffix in IMAGE_SUFFIXES:
        return ingest_image(data, filename)
    raise UnsupportedDocumentError(
        f"Unsupported file type '{suffix or filename}'. "
        "Use pdf, xlsx, xls, csv, docx, jpg, png, or webp."
    )
