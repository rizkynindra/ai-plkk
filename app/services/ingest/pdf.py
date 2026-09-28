from __future__ import annotations

from collections import defaultdict
from io import BytesIO

import pdfplumber
import pymupdf
from PIL import Image

from app.config import settings
from app.schemas import DocumentContent, ExtractedTable
from app.services.ingest import cell_str
from app.services.ingest.image import ocr_pil_image

ROW_Y_TOLERANCE = 8
HEADER_WORD_GAP = 18


def ingest_pdf(data: bytes, filename: str) -> DocumentContent:
    pages_text: list[str] = []
    tables: list[ExtractedTable] = []
    used_ocr = False

    with pdfplumber.open(BytesIO(data)) as pdf:
        for index, page in enumerate(pdf.pages):
            page_text = (page.extract_text() or "").strip()
            if len(page_text) < settings.pdf_scan_text_threshold:
                ocr_text = _ocr_pdf_page(data, index)
                if ocr_text:
                    used_ocr = True
                    page_text = ocr_text
            if page_text:
                pages_text.append(page_text)
            for raw_table in page.extract_tables() or []:
                rows = [[cell_str(cell) for cell in row] for row in raw_table if row]
                rows = [row for row in rows if any(row)]
                if not rows:
                    continue
                tables.append(ExtractedTable(headers=rows[0], rows=rows[1:]))

    if not tables:
        tables = _stitch_split_tables(_tables_from_pdf_words(data))

    return DocumentContent(
        filename=filename,
        media_type="application/pdf",
        source="ocr" if used_ocr and not tables else "pdf",
        pages_text=pages_text,
        tables=tables,
    )


def _ocr_pdf_page(data: bytes, page_index: int) -> str:
    if not settings.ocr_enabled:
        return ""
    document = pymupdf.open(stream=data, filetype="pdf")
    try:
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        return ocr_pil_image(image)
    finally:
        document.close()


def _tables_from_pdf_words(data: bytes) -> list[ExtractedTable]:
    document = pymupdf.open(stream=data, filetype="pdf")
    tables: list[ExtractedTable] = []
    try:
        for page in document:
            table = _table_from_words(page.get_text("words"))
            if table:
                tables.append(table)
    finally:
        document.close()
    return tables


def _table_from_words(words: list[tuple]) -> ExtractedTable | None:
    if not words:
        return None
    rows_by_y: dict[int, list[tuple]] = defaultdict(list)
    for word in words:
        y_key = int(round(word[1] / ROW_Y_TOLERANCE))
        rows_by_y[y_key].append(word)
    ordered_rows = [sorted(rows_by_y[key], key=lambda item: item[0]) for key in sorted(rows_by_y)]
    if len(ordered_rows) < 2:
        return None
    headers, anchors = _header_cells(ordered_rows[0])
    if len(headers) < 2:
        return None
    body = [_assign_row(raw_row, anchors) for raw_row in ordered_rows[1:]]
    return ExtractedTable(headers=headers, rows=body)


def _header_cells(header_words: list[tuple]) -> tuple[list[str], list[float]]:
    groups: list[list[tuple]] = []
    current: list[tuple] = []
    for word in header_words:
        if current and word[0] - current[-1][2] > HEADER_WORD_GAP:
            groups.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        groups.append(current)
    headers = [" ".join(part[4] for part in group) for group in groups]
    left_edges = [min(part[0] for part in group) for group in groups]
    return headers, left_edges


def _assign_row(row_words: list[tuple], left_edges: list[float]) -> list[str]:
    buckets: list[list[str]] = [[] for _ in left_edges]
    for word in row_words:
        x0 = word[0]
        column = 0
        for index, edge in enumerate(left_edges):
            if x0 + 1 >= edge:
                column = index
        buckets[column].append(word[4])
    return [" ".join(bucket) for bucket in buckets]


def _stitch_split_tables(tables: list[ExtractedTable]) -> list[ExtractedTable]:
    if len(tables) < 2:
        return tables
    stitched: list[ExtractedTable] = []
    index = 0
    while index < len(tables):
        if index + 1 < len(tables) and _is_split_cost_table(tables[index], tables[index + 1]):
            left, right = tables[index], tables[index + 1]
            row_count = min(len(left.rows), len(right.rows))
            stitched.append(
                ExtractedTable(
                    headers=left.headers + right.headers,
                    rows=[left.rows[row] + right.rows[row] for row in range(row_count)],
                )
            )
            index += 2
            continue
        stitched.append(tables[index])
        index += 1
    return stitched


def _is_split_cost_table(left: ExtractedTable, right: ExtractedTable) -> bool:
    left_blob = " ".join(left.headers).lower()
    right_blob = " ".join(right.headers).lower()
    left_has_item = "item" in left_blob or "uraian" in left_blob
    right_has_price = "tarif" in right_blob or "harga" in right_blob or "biaya" in right_blob
    left_missing_price = "tarif" not in left_blob and "harga" not in left_blob
    return left_has_item and right_has_price and left_missing_price
