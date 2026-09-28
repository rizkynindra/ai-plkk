from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from app.schemas import ExtractedTable
from app.services.ingest.router import ingest_file
from app.services.money import parse_idr_amount

CODE_RE = re.compile(r"^([A-Z]{2,3}\d{4})\b\s*(.*)$")
GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?")
SKIP_NAME_MARKERS = ("daftar isi", "kata pengantar", "ketentuan umum")


@dataclass
class CatalogItem:
    item_name: str
    tariff: float | None
    item_code: str = ""
    kelompok: str = ""
    tariff_note: str = ""
    source_page: int | None = None


@dataclass
class CatalogDraft:
    group_name: str
    branch_name: str
    city: str
    address: str
    code: str
    aliases: list[str]
    effective_date: str
    source_filename: str
    method: str
    items: list[CatalogItem] = field(default_factory=list)


def normalize_item_name(name: str) -> str:
    text = name.lower().replace("¼", " 1/4 ").replace("½", " 1/2 ").replace("¾", " 3/4 ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def parse_pks_document(data: bytes, filename: str) -> CatalogDraft:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(data, filename)
    content = ingest_file(data, filename)
    items = _parse_tables(content.tables)
    if not items:
        items = _parse_text_pages(content.pages_text)
    suggested = _suggest_hospital("\n".join(content.pages_text), filename)
    suggested.source_filename = filename
    suggested.method = "table" if content.tables else "text"
    suggested.items = items
    return suggested


def _parse_pdf(data: bytes, filename: str) -> CatalogDraft:
    document = pymupdf.open(stream=data, filetype="pdf")
    pages: list[str] = []
    try:
        for index in range(document.page_count):
            pages.append(document.load_page(index).get_text("text") or "")
    finally:
        document.close()
    items = _parse_text_pages(pages)
    suggested = _suggest_hospital("\n".join(pages[:6]), filename)
    suggested.source_filename = filename
    suggested.method = "pdf-text"
    suggested.items = items
    return suggested


def _parse_text_pages(pages: list[str]) -> list[CatalogItem]:
    items: list[CatalogItem] = []
    kelompok = ""
    for page_number, page_text in enumerate(pages, start=1):
        lines = [re.sub(r"\s+", " ", line).strip() for line in page_text.splitlines()]
        lines = [line for line in lines if line]
        index = 0
        while index < len(lines):
            line = lines[index]
            if _looks_like_section(line):
                kelompok = line
                index += 1
                continue
            match = CODE_RE.match(line)
            if not match:
                index += 1
                continue
            code, remainder = match.groups()
            block = [remainder] if remainder else []
            index += 1
            while index < len(lines) and not CODE_RE.match(lines[index]) and not _looks_like_section(lines[index]):
                if lines[index].isdigit() and len(lines[index]) <= 3:
                    index += 1
                    continue
                block.append(lines[index])
                if len(block) >= 8:
                    break
                index += 1
            items.extend(_items_from_code_block(code, block, kelompok, page_number))
    return _dedupe_items(items)


def _items_from_code_block(
    code: str,
    block: list[str],
    kelompok: str,
    page_number: int,
) -> list[CatalogItem]:
    blob = " ".join(block)
    amounts = [parse_idr_amount(match.group(0)) for match in GROUPED_AMOUNT.finditer(blob)]
    amounts = [amount for amount in amounts if amount is not None and amount >= 1000]
    name = GROUPED_AMOUNT.sub(" ", blob)
    name = re.sub(r"\s+", " ", name).strip(" -")
    if not name:
        return []
    note = ""
    if not amounts and re.search(r"%|maks", blob, re.I):
        note = blob
        return [
            CatalogItem(
                item_name=name or blob,
                tariff=None,
                item_code=code,
                kelompok=kelompok,
                tariff_note=note,
                source_page=page_number,
            )
        ]
    if not amounts:
        return []
    if len(amounts) == 1:
        return [
            CatalogItem(
                item_name=name,
                tariff=amounts[0],
                item_code=code,
                kelompok=kelompok,
                source_page=page_number,
            )
        ]
    class_names = _class_labels(name)
    if class_names and len(class_names) == len(amounts):
        return [
            CatalogItem(
                item_name=f"{_base_name(name)} {label}",
                tariff=amount,
                item_code=code,
                kelompok=kelompok,
                source_page=page_number,
            )
            for label, amount in zip(class_names, amounts)
        ]
    return [
        CatalogItem(
            item_name=name,
            tariff=amounts[0],
            item_code=code,
            kelompok=kelompok,
            source_page=page_number,
        )
    ]


def _class_labels(name: str) -> list[str]:
    upper = name.upper()
    if "KELAS" in upper or "VIP" in upper or "ICCU" in upper:
        return []
    if "DU/DRG" in upper or "SUB SPESIALIS" in upper:
        return ["DU/DRG", "DR/DRG SPESIALIS", "SUB SPESIALIS", "PROFESOR"]
    return []


def _base_name(name: str) -> str:
    return re.sub(r"\b(DU/DRG|DR/DRG SPESIALIS|SUB SPESIALIS|PROFESOR|KELAS)\b.*", "", name, flags=re.I).strip()


def _looks_like_section(line: str) -> bool:
    if CODE_RE.match(line):
        return False
    if GROUPED_AMOUNT.search(line):
        return False
    if len(line) > 80:
        return False
    lowered = line.lower()
    if any(marker in lowered for marker in SKIP_NAME_MARKERS):
        return False
    return line.isupper() or line.endswith(":") or line in {
        "BIAYA ADMINISTRASI",
        "RAWAT JALAN & IGD",
        "KLINIK INTERNASIONAL",
        "TELEMEDICINE",
        "KONSULTASI / VISITE RAWAT INAP",
        "KAMAR PERAWATAN",
        "RAWAT INAP",
    }


def _parse_tables(tables: list[ExtractedTable]) -> list[CatalogItem]:
    items: list[CatalogItem] = []
    for table in tables:
        headers = [cell.lower() for cell in table.headers]
        name_idx = _first_header(headers, ("nama tindakan", "uraian", "item", "administrasi", "konsultasi", "nama"))
        tariff_idx = _first_header(headers, ("tarif pks", "tarif", "harga"))
        code_idx = _first_header(headers, ("code", "kode"))
        group_idx = _first_header(headers, ("kelompok", "section"))
        if name_idx is None or tariff_idx is None:
            continue
        for row in table.rows:
            name = _cell(row, name_idx)
            if not name:
                continue
            tariff = parse_idr_amount(_cell(row, tariff_idx))
            note = _cell(row, tariff_idx) if tariff is None else ""
            items.append(
                CatalogItem(
                    item_name=name,
                    tariff=tariff,
                    item_code=_cell(row, code_idx) if code_idx is not None else "",
                    kelompok=_cell(row, group_idx) if group_idx is not None else "",
                    tariff_note=note,
                )
            )
    return _dedupe_items(items)


def _first_header(headers: list[str], names: tuple[str, ...]) -> int | None:
    for index, header in enumerate(headers):
        if any(name in header for name in names):
            return index
    return None


def _cell(row: list[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return str(row[index]).strip()


def _dedupe_items(items: list[CatalogItem]) -> list[CatalogItem]:
    seen: set[tuple] = set()
    kept: list[CatalogItem] = []
    for item in items:
        key = (item.item_code, normalize_item_name(item.item_name), item.tariff)
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _suggest_hospital(text: str, filename: str) -> CatalogDraft:
    city = ""
    if re.search(r"\bjakarta\b", text, re.I):
        city = "Jakarta"
    elif re.search(r"\bmalang\b", text, re.I):
        city = "Malang"
    group = "Rumah Sakit PELNI" if re.search(r"pelni", text + filename, re.I) else Path(filename).stem
    effective = ""
    date_match = re.search(r"(\d{1,2})\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\s+(20\d{2})", text, re.I)
    months = {
        "januari": "01",
        "februari": "02",
        "maret": "03",
        "april": "04",
        "mei": "05",
        "juni": "06",
        "juli": "07",
        "agustus": "08",
        "september": "09",
        "oktober": "10",
        "november": "11",
        "desember": "12",
    }
    if date_match and "agustus" in text.lower() and "2024" in text:
        effective = "2024-08-01"
        start_match = re.search(r"terhitung mulai tanggal\s+(\d{1,2})\s+(\w+)\s+(20\d{2})", text, re.I)
        if start_match:
            day, month, year = start_match.groups()
            effective = f"{year}-{months.get(month.lower(), '01')}-{int(day):02d}"
    elif date_match:
        day, month, year = date_match.groups()
        effective = f"{year}-{months.get(month.lower(), '01')}-{int(day):02d}"
    branch = f"{group} {city}".strip()
    return CatalogDraft(
        group_name=group,
        branch_name=branch,
        city=city,
        address="",
        code="",
        aliases=[value for value in {group.lower(), "pelni", f"pelni {city.lower()}".strip()} if value],
        effective_date=effective,
        source_filename=filename,
        method="pdf-text",
        items=[],
    )
