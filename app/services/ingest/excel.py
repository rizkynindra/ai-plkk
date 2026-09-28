from __future__ import annotations

from io import BytesIO

import pandas as pd

from app.schemas import DocumentContent, ExtractedTable
from app.services.ingest import cell_str

EXCEL_SUFFIXES = {".xlsx", ".xls", ".xlsm"}
CSV_SUFFIXES = {".csv"}


def ingest_spreadsheet(data: bytes, filename: str, suffix: str) -> DocumentContent:
    buffer = BytesIO(data)
    if suffix in CSV_SUFFIXES:
        frames = {"Sheet1": pd.read_csv(buffer, dtype=str, header=None, keep_default_na=False)}
    elif suffix == ".xls":
        frames = _read_xls(buffer)
    else:
        frames = pd.read_excel(buffer, sheet_name=None, header=None, dtype=str, engine="openpyxl")

    tables: list[ExtractedTable] = []
    pages: list[str] = []
    for sheet_name, frame in frames.items():
        rows = [[cell_str(value) for value in row] for row in frame.itertuples(index=False, name=None)]
        rows = _trim_empty(rows)
        if not rows:
            continue
        header = rows[0]
        body = rows[1:] if len(rows) > 1 else []
        tables.append(ExtractedTable(headers=header, rows=body))
        preview_lines = [" | ".join(row) for row in rows[:40]]
        pages.append(f"{sheet_name}\n" + "\n".join(preview_lines))

    return DocumentContent(
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        source="excel" if suffix in EXCEL_SUFFIXES else "csv",
        pages_text=pages,
        tables=tables,
    )


def _read_xls(buffer: BytesIO):
    try:
        return pd.read_excel(buffer, sheet_name=None, header=None, dtype=str, engine="calamine")
    except Exception:
        buffer.seek(0)
        return pd.read_excel(buffer, sheet_name=None, header=None, dtype=str, engine="xlrd")


def _trim_empty(rows: list[list[str]]) -> list[list[str]]:
    cleaned: list[list[str]] = []
    for row in rows:
        if any(cell.strip() for cell in row):
            cleaned.append([cell.strip() for cell in row])
    return cleaned
