from __future__ import annotations

from pathlib import Path

from app.schemas import ClassificationResult, ConversionPreview
from app.services.classify import classify_document
from app.services.extract import extract_cost_lines
from app.services.ingest.router import ingest_file
from app.services.template import build_template_workbook
from app.services.vision import extract_image_cost_lines_with_vision, extract_pdf_cost_lines_with_vision


class NotClaimInvoiceError(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class EmptyExtractionError(ValueError):
    pass


def convert_document(data: bytes, filename: str) -> tuple[ConversionPreview, bytes]:
    content = ingest_file(data, filename)
    classification = classify_document(content)
    if not classification.is_claim_invoice and classification.confidence >= 0.9:
        raise NotClaimInvoiceError(classification.reason)
    lines = extract_cost_lines(content)
    suffix = Path(filename).suffix.lower()
    if not lines and suffix == ".pdf":
        lines = extract_pdf_cost_lines_with_vision(data)
        if lines:
            classification = ClassificationResult(
                is_claim_invoice=True,
                confidence=0.9,
                reason="Qwen3-VL found billed cost lines on scanned pages.",
                method="qwen3-vl",
            )
    if not lines and suffix in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}:
        lines = extract_image_cost_lines_with_vision(data)
        if lines:
            classification = ClassificationResult(
                is_claim_invoice=True,
                confidence=0.9,
                reason="Qwen3-VL found billed cost lines on the uploaded image.",
                method="qwen3-vl",
            )

    if not classification.is_claim_invoice:
        raise NotClaimInvoiceError(classification.reason)
    writable = [line for line in lines if not line.needs_review]
    if not writable:
        raise EmptyExtractionError("Could not extract billed cost lines from this invoice.")

    workbook = build_template_workbook(writable)
    preview = ConversionPreview(
        filename=filename,
        source=content.source,
        classification=classification,
        lines=lines,
        written_count=len(writable),
        review_count=sum(1 for line in lines if line.needs_review),
    )
    return preview, workbook
