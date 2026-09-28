from __future__ import annotations

import io
import logging

from PIL import Image

from app.config import settings
from app.schemas import DocumentContent, ExtractedTable

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def ingest_image(data: bytes, filename: str) -> DocumentContent:
    text = ocr_image_bytes(data)
    tables = _rows_from_ocr_text(text)
    return DocumentContent(
        filename=filename,
        media_type="image/*",
        source="ocr",
        pages_text=[text] if text else [],
        tables=tables,
    )


def ocr_image_bytes(data: bytes) -> str:
    image = Image.open(io.BytesIO(data))
    return ocr_pil_image(image)


def ocr_pil_image(image: Image.Image) -> str:
    if not settings.ocr_enabled:
        return ""
    try:
        import pytesseract
    except ImportError:
        logger.warning("pytesseract is not installed")
        return ""
    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        return ""
    try:
        return pytesseract.image_to_string(image, lang="ind+eng") or ""
    except Exception:
        try:
            return pytesseract.image_to_string(image) or ""
        except Exception:
            logger.warning("OCR failed", exc_info=True)
            return ""


def _rows_from_ocr_text(text: str) -> list[ExtractedTable]:
    rows = [line.split() for line in text.splitlines() if line.strip()]
    if not rows:
        return []
    return [ExtractedTable(headers=rows[0], rows=rows[1:])]
