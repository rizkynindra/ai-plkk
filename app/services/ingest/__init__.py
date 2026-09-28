from __future__ import annotations

from app.schemas import DocumentContent, ExtractedTable


def tables_as_text(tables: list[ExtractedTable], limit: int = 8000) -> str:
    chunks: list[str] = []
    for table in tables:
        header = " | ".join(table.headers)
        if header:
            chunks.append(header)
        for row in table.rows:
            chunks.append(" | ".join(row))
        chunks.append("")
    return "\n".join(chunks)[:limit]


def joined_text(content: DocumentContent, limit: int = 12_000) -> str:
    pages = "\n\n".join(content.pages_text)
    tables = tables_as_text(content.tables)
    return f"{pages}\n\n{tables}".strip()[:limit]


def cell_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
