from __future__ import annotations

import re

from app.schemas import ClassificationResult, DocumentContent
from app.services.ingest import joined_text, tables_as_text
from app.services.llm import classify_with_llm, llm_available

INVOICE_HEADERS = {
    "item biaya",
    "uraian",
    "tarif",
    "harga satuan",
    "biaya",
    "jumlah",
    "qty",
}
INVOICE_KEYWORDS = {
    "rincian biaya",
    "tagihan",
    "invoice",
    "nota",
    "klaim",
    "item biaya",
}
IKS_MARKERS = {
    "kelompok",
    "tarif pks",
    "daftar biaya sesuai iks",
    "no. iks",
}
TARIF_BOOK_MARKERS = {
    "daftar isi",
    "kata pengantar",
    "memberlakukan tarif baru",
    "ketentuan umum",
    "nama tindakan",
}
LETTER_MARKERS = {
    "yang bertanda tangan",
    "nik",
    "kartu tanda penduduk",
    "dengan hormat",
}


def classify_document(content: DocumentContent) -> ClassificationResult:
    heuristic = _heuristic(content)
    if heuristic.confidence >= 0.8 or heuristic.confidence <= 0.2:
        return heuristic
    if not llm_available():
        return heuristic
    payload = classify_with_llm(joined_text(content), tables_as_text(content.tables))
    if not payload:
        return heuristic
    return ClassificationResult(
        is_claim_invoice=bool(payload.get("is_claim_invoice")),
        confidence=float(payload.get("confidence") or 0.5),
        reason=str(payload.get("reason") or "llm classification"),
        method="llm",
    )


def _heuristic(content: DocumentContent) -> ClassificationResult:
    blob = _normalize(joined_text(content, limit=20_000))
    header_blob = _normalize(" ".join(" ".join(table.headers) for table in content.tables))
    filename = _normalize(content.filename)

    if "tarif pelni" in filename or filename.startswith("tarif "):
        return ClassificationResult(
            is_claim_invoice=False,
            confidence=0.97,
            reason="Looks like a hospital tariff book (PKS), not a billed claim invoice.",
            method="heuristic",
        )
    tarif_hits = sum(1 for marker in TARIF_BOOK_MARKERS if marker in blob)
    if tarif_hits >= 2 and ("tarif" in blob or re.search(r"\b[a-z]{2}\d{4}\b", blob)):
        return ClassificationResult(
            is_claim_invoice=False,
            confidence=0.96,
            reason="Looks like a hospital tariff book (PKS), not a billed claim invoice.",
            method="heuristic",
        )

    if any(marker in blob or marker in header_blob for marker in IKS_MARKERS):
        if "tarif pks" in header_blob or "kelompok" in header_blob:
            return ClassificationResult(
                is_claim_invoice=False,
                confidence=0.95,
                reason="Looks like an IKS tariff catalog, not a billed claim invoice.",
                method="heuristic",
            )

    if any(marker in blob for marker in LETTER_MARKERS) and not any(
        marker in blob for marker in INVOICE_KEYWORDS
    ):
        return ClassificationResult(
            is_claim_invoice=False,
            confidence=0.85,
            reason="Looks like a letter or identity document.",
            method="heuristic",
        )

    invoice_header_hits = sum(1 for token in INVOICE_HEADERS if token in header_blob)
    has_keyword = any(token in blob for token in INVOICE_KEYWORDS)
    has_rows = any(table.rows for table in content.tables)

    if invoice_header_hits >= 3 and has_rows:
        return ClassificationResult(
            is_claim_invoice=True,
            confidence=0.92,
            reason="Table headers match a billed cost breakdown.",
            method="heuristic",
        )
    if has_keyword and has_rows:
        return ClassificationResult(
            is_claim_invoice=True,
            confidence=0.8,
            reason="Invoice keywords plus line-item table.",
            method="heuristic",
        )
    if invoice_header_hits >= 2:
        return ClassificationResult(
            is_claim_invoice=True,
            confidence=0.65,
            reason="Partial cost-table headers; confirm with extraction.",
            method="heuristic",
        )
    if has_keyword and ("item biaya" in blob or "tarif" in blob):
        return ClassificationResult(
            is_claim_invoice=True,
            confidence=0.72,
            reason="Invoice field labels found in document text.",
            method="heuristic",
        )
    if not blob.strip():
        return ClassificationResult(
            is_claim_invoice=False,
            confidence=0.9,
            reason="Document has no extractable text.",
            method="heuristic",
        )
    return ClassificationResult(
        is_claim_invoice=False,
        confidence=0.45,
        reason="No clear billed invoice table.",
        method="heuristic",
    )


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
