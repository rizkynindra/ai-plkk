from __future__ import annotations

import re

from app.schemas import CostLine, DocumentContent, ExtractedTable
from app.services.ingest import joined_text, tables_as_text
from app.services.llm import extract_with_llm, llm_available
from app.services.money import amount_in_source, amounts_in_text, parse_idr_amount

ITEM_HEADERS = {
    "item biaya",
    "uraian",
    "nama item",
    "keterangan",
    "deskripsi",
    "item",
    "layanan",
    "nama",
    "uraian pekerjaan",
}
QTY_HEADERS = {"jumlah", "qty", "kuantitas", "volume", "qty."}
TARIFF_HEADERS = {"tarif", "harga", "harga satuan", "unit price", "rate", "harga/unit"}
COST_HEADERS = {
    "biaya (setelah dikurangi diskon)",
    "biaya",
    "total",
    "jumlah biaya",
    "subtotal",
    "nilai",
    "harga total",
    "biaya setelah dikurangi diskon",
}
SKIP_NAME_PREFIXES = {"total", "subtotal", "jumlah", "grand total"}


def extract_cost_lines(content: DocumentContent) -> list[CostLine]:
    source_amounts = _source_amounts(content)
    heuristic_lines = _extract_from_tables(content.tables)
    if heuristic_lines:
        return _guard_lines(heuristic_lines, source_amounts, require_source=False)

    if llm_available():
        payload = extract_with_llm(joined_text(content), tables_as_text(content.tables))
        llm_lines = _lines_from_payload(payload)
        if llm_lines:
            return _guard_lines(llm_lines, source_amounts, require_source=True)

    return []


def _extract_from_tables(tables: list[ExtractedTable]) -> list[CostLine]:
    mapped: list[CostLine] = []
    for table in tables:
        mapping = _column_map(table.headers)
        if mapping.get("item") is None or (mapping.get("tariff") is None and mapping.get("cost") is None):
            continue
        has_qty_col = mapping.get("qty") is not None
        has_tariff_col = mapping.get("tariff") is not None
        has_cost_col = mapping.get("cost") is not None
        jumlah_is_money = (
            mapping.get("qty") is not None
            and not has_tariff_col
            and not has_cost_col
        )
        for raw in table.rows:
            line = _row_to_line(raw, mapping, has_qty_col, jumlah_is_money)
            if line:
                mapped.append(line)
    _renumber(mapped)
    return mapped


def _row_to_line(
    raw: list[str],
    mapping: dict[str, int | None],
    has_qty_col: bool,
    jumlah_is_money: bool,
) -> CostLine | None:
    item = _cell(raw, mapping.get("item"))
    item = re.sub(r"^\d+\s+", "", item).strip()
    if not item or _normalize(item) in SKIP_NAME_PREFIXES:
        return None
    if parse_idr_amount(item) is not None and len(item.split()) <= 1:
        return None

    qty = parse_idr_amount(_cell(raw, mapping.get("qty"))) if has_qty_col and not jumlah_is_money else 1.0
    if qty is None or qty <= 0:
        qty = 1.0

    tariff = parse_idr_amount(_cell(raw, mapping.get("tariff")))
    cost = parse_idr_amount(_cell(raw, mapping.get("cost")))
    if jumlah_is_money:
        cost = parse_idr_amount(_cell(raw, mapping.get("qty")))

    if tariff is None and cost is None:
        return None
    if tariff is None and cost is not None:
        tariff = cost / qty if qty else cost
    if cost is None and tariff is not None:
        cost = qty * tariff

    return CostLine(
        sequence_no=0,
        item_name=item,
        quantity=qty,
        tariff=float(tariff),
        discounted_cost=float(cost),
    )


def _column_map(headers: list[str]) -> dict[str, int | None]:
    normalized = [_normalize(header) for header in headers]
    return {
        "item": _first_index(normalized, ITEM_HEADERS),
        "qty": _first_index(normalized, QTY_HEADERS),
        "tariff": _first_index(normalized, TARIFF_HEADERS),
        "cost": _first_index(normalized, COST_HEADERS),
    }


def _first_index(normalized: list[str], aliases: set[str]) -> int | None:
    for index, header in enumerate(normalized):
        if header in aliases:
            return index
    for alias in sorted(aliases, key=len, reverse=True):
        if len(alias) < 8:
            continue
        for index, header in enumerate(normalized):
            if alias in header:
                return index
    return None


def _lines_from_payload(payload: dict | None) -> list[CostLine]:
    if not payload:
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    lines: list[CostLine] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("item_name") or "").strip()
        tariff = parse_idr_amount(item.get("tariff"))
        qty = parse_idr_amount(item.get("quantity")) or 1.0
        cost = parse_idr_amount(item.get("discounted_cost"))
        if not name or tariff is None:
            continue
        if cost is None:
            cost = qty * tariff
        lines.append(
            CostLine(
                sequence_no=len(lines) + 1,
                item_name=name,
                quantity=qty,
                tariff=tariff,
                discounted_cost=cost,
            )
        )
    return lines


def _guard_lines(
    lines: list[CostLine],
    source_amounts: set[float],
    require_source: bool,
) -> list[CostLine]:
    guarded: list[CostLine] = []
    for index, line in enumerate(lines, start=1):
        line.sequence_no = index
        if not require_source:
            guarded.append(line)
            continue
        tariff_ok = amount_in_source(line.tariff, source_amounts)
        cost_ok = amount_in_source(line.discounted_cost, source_amounts) or amount_in_source(
            line.quantity * line.tariff, source_amounts
        )
        if tariff_ok and cost_ok:
            guarded.append(line)
            continue
        line.needs_review = True
        line.review_reason = "Amount was not found in the source document."
        guarded.append(line)
    return guarded


def _source_amounts(content: DocumentContent) -> set[float]:
    amounts = amounts_in_text(joined_text(content, limit=50_000))
    for table in content.tables:
        for header in table.headers:
            parsed = parse_idr_amount(header)
            if parsed is not None:
                amounts.add(parsed)
        for row in table.rows:
            for cell in row:
                parsed = parse_idr_amount(cell)
                if parsed is not None:
                    amounts.add(parsed)
    return amounts


def _renumber(lines: list[CostLine]) -> None:
    for index, line in enumerate(lines, start=1):
        line.sequence_no = index


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
