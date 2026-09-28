from __future__ import annotations

from app.services.agreements.match import compare_lines
from app.services.agreements.parse import CatalogDraft, CatalogItem, parse_pks_document
from app.services.agreements.store import connect
from app.schemas import CostLine


def preview_pks(data: bytes, filename: str) -> dict:
    draft = parse_pks_document(data, filename)
    if not draft.items:
        raise ValueError("Could not extract PKS tariff rows from this file.")
    return _draft_payload(draft)


def save_agreement(draft: CatalogDraft) -> dict:
    if not draft.items:
        raise ValueError("No PKS items to store.")
    connection = connect()
    group_id = _upsert_group(draft.group_name)
    branch_id = _upsert_branch(group_id, draft)
    cursor = connection.execute(
        """
        INSERT INTO agreements (branch_id, source_filename, effective_date)
        VALUES (?, ?, ?)
        """,
        (branch_id, draft.source_filename, draft.effective_date),
    )
    agreement_id = int(cursor.lastrowid)
    connection.executemany(
        """
        INSERT INTO agreement_items (
            agreement_id, kelompok, item_code, item_name, normalized_name, tariff, tariff_note
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                agreement_id,
                item.kelompok,
                item.item_code,
                item.item_name,
                _norm(item.item_name),
                item.tariff,
                item.tariff_note,
            )
            for item in draft.items
        ],
    )
    connection.commit()
    return {
        "agreement_id": agreement_id,
        "branch_id": branch_id,
        "item_count": len(draft.items),
        "group_name": draft.group_name,
        "branch_name": draft.branch_name,
    }


def list_hospitals() -> list[dict]:
    rows = connect().execute(
        """
        SELECT
            b.id AS branch_id,
            g.name AS group_name,
            b.name AS branch_name,
            b.city,
            b.address,
            b.code,
            b.aliases,
            (
                SELECT COUNT(*)
                FROM agreement_items i
                JOIN agreements a ON a.id = i.agreement_id
                WHERE a.branch_id = b.id
                  AND a.id = (SELECT MAX(id) FROM agreements WHERE branch_id = b.id)
            ) AS item_count
        FROM branches b
        JOIN hospital_groups g ON g.id = b.group_id
        ORDER BY g.name, b.name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def latest_catalog(branch_id: int) -> list[CatalogItem]:
    connection = connect()
    agreement = connection.execute(
        "SELECT id FROM agreements WHERE branch_id = ? ORDER BY id DESC LIMIT 1",
        (branch_id,),
    ).fetchone()
    if agreement is None:
        return []
    rows = connection.execute(
        """
        SELECT kelompok, item_code, item_name, tariff, tariff_note
        FROM agreement_items
        WHERE agreement_id = ?
        """,
        (int(agreement["id"]),),
    ).fetchall()
    return [
        CatalogItem(
            item_name=row["item_name"],
            tariff=row["tariff"],
            item_code=row["item_code"],
            kelompok=row["kelompok"],
            tariff_note=row["tariff_note"],
        )
        for row in rows
    ]


def get_branch_catalog(branch_id: int) -> dict | None:
    branch = next((row for row in list_hospitals() if int(row["branch_id"]) == branch_id), None)
    if branch is None:
        return None
    items = latest_catalog(branch_id)
    payload = dict(branch)
    payload["items"] = [
        {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "kelompok": item.kelompok,
            "tariff": item.tariff,
            "tariff_note": item.tariff_note,
        }
        for item in items
    ]
    return payload


def compare_branch_lines(branch_id: int, lines: list[CostLine]) -> dict:
    catalog = latest_catalog(branch_id)
    compared = compare_lines(lines, catalog)
    counts = {
        "matched": 0,
        "price_mismatch": 0,
        "unmatched": 0,
        "ambiguous": 0,
    }
    for row in compared:
        status = row.get("match_status") or "unmatched"
        if status not in counts:
            counts[status] = 0
        counts[status] += 1
    return {
        "branch_id": branch_id,
        "catalog_size": len(catalog),
        "counts": counts,
        "lines": compared,
    }


def draft_from_payload(payload: dict) -> CatalogDraft:
    items = [
        CatalogItem(
            item_name=str(item.get("item_name") or ""),
            tariff=item.get("tariff"),
            item_code=str(item.get("item_code") or ""),
            kelompok=str(item.get("kelompok") or ""),
            tariff_note=str(item.get("tariff_note") or ""),
            source_page=item.get("source_page"),
        )
        for item in payload.get("items") or []
        if str(item.get("item_name") or "").strip()
    ]
    aliases = payload.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [part.strip() for part in aliases.split(",") if part.strip()]
    return CatalogDraft(
        group_name=str(payload.get("group_name") or "").strip() or "Hospital",
        branch_name=str(payload.get("branch_name") or "").strip() or str(payload.get("group_name") or "Branch"),
        city=str(payload.get("city") or "").strip(),
        address=str(payload.get("address") or "").strip(),
        code=str(payload.get("code") or "").strip(),
        aliases=[str(alias) for alias in aliases],
        effective_date=str(payload.get("effective_date") or "").strip(),
        source_filename=str(payload.get("source_filename") or "pks.pdf"),
        method=str(payload.get("method") or "manual"),
        items=items,
    )


def _upsert_group(name: str) -> int:
    connection = connect()
    connection.execute("INSERT OR IGNORE INTO hospital_groups (name) VALUES (?)", (name,))
    row = connection.execute("SELECT id FROM hospital_groups WHERE name = ?", (name,)).fetchone()
    connection.commit()
    return int(row["id"])


def _upsert_branch(group_id: int, draft: CatalogDraft) -> int:
    connection = connect()
    aliases = ",".join(draft.aliases)
    existing = connection.execute(
        "SELECT id FROM branches WHERE group_id = ? AND name = ?",
        (group_id, draft.branch_name),
    ).fetchone()
    if existing:
        connection.execute(
            """
            UPDATE branches
            SET city = ?, address = ?, code = ?, aliases = ?
            WHERE id = ?
            """,
            (draft.city, draft.address, draft.code, aliases, int(existing["id"])),
        )
        connection.commit()
        return int(existing["id"])
    cursor = connection.execute(
        """
        INSERT INTO branches (group_id, name, city, address, code, aliases)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (group_id, draft.branch_name, draft.city, draft.address, draft.code, aliases),
    )
    connection.commit()
    return int(cursor.lastrowid)


def _draft_payload(draft: CatalogDraft) -> dict:
    return {
        "group_name": draft.group_name,
        "branch_name": draft.branch_name,
        "city": draft.city,
        "address": draft.address,
        "code": draft.code,
        "aliases": draft.aliases,
        "effective_date": draft.effective_date,
        "source_filename": draft.source_filename,
        "method": draft.method,
        "item_count": len(draft.items),
        "items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "kelompok": item.kelompok,
                "tariff": item.tariff,
                "tariff_note": item.tariff_note,
                "source_page": item.source_page,
            }
            for item in draft.items
        ],
    }


def _norm(name: str) -> str:
    from app.services.agreements.parse import normalize_item_name

    return normalize_item_name(name)
