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
            agreement_id, kelompok, item_code, item_name, normalized_name,
            tariff, tariff_note, group_code, source_page
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                item.group_code,
                "" if item.source_page is None else str(item.source_page),
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
        SELECT kelompok, item_code, item_name, tariff, tariff_note, group_code, source_page
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
            group_code=row["group_code"] or "",
            source_page=_stored_page(row["source_page"]),
        )
        for row in rows
    ]


def get_branch_catalog(branch_id: int) -> dict | None:
    branch = next((row for row in list_hospitals() if int(row["branch_id"]) == branch_id), None)
    if branch is None:
        return None
    items = latest_catalog(branch_id)
    payload = dict(branch)
    payload["items"] = [_tariff_row(item, str(branch["branch_name"] or "")) for item in items]
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
    items = []
    for raw in payload.get("items") or []:
        item = _item_from_payload(raw)
        if item is not None:
            items.append(item)
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
        "items": [_tariff_row(item, draft.branch_name) for item in draft.items],
    }


TARIFF_COLUMNS = (
    "kode_master",
    "kategori_bpjs",
    "hospital_name",
    "nama",
    "group_code",
    "price",
    "price_base",
    "price_final",
    "price_basis",
    "source_page",
)


def _tariff_row(item: CatalogItem, hospital_name: str) -> dict:
    values = {
        "kode_master": item.item_code,
        "kategori_bpjs": item.kelompok,
        "hospital_name": hospital_name,
        "nama": item.item_name,
        "group_code": item.group_code,
        "price": item.tariff,
        "price_base": item.tariff,
        "price_final": item.tariff,
        "price_basis": item.tariff_note,
        "source_page": item.source_page,
    }
    return {column: values[column] for column in TARIFF_COLUMNS}


def _item_from_payload(raw: dict) -> CatalogItem | None:
    name = str(raw.get("nama") or raw.get("item_name") or "").strip()
    if not name:
        return None
    if "price_final" in raw and raw.get("price_final") is not None:
        tariff = raw.get("price_final")
    elif raw.get("price") is not None:
        tariff = raw.get("price")
    else:
        tariff = raw.get("tariff")
    source_page = _stored_page(raw.get("source_page"))
    return CatalogItem(
        item_name=name,
        tariff=tariff,
        item_code=str(raw.get("kode_master") or raw.get("item_code") or ""),
        kelompok=str(raw.get("kategori_bpjs") or raw.get("kelompok") or ""),
        tariff_note=str(raw.get("price_basis") or raw.get("tariff_note") or ""),
        group_code=str(raw.get("group_code") or ""),
        source_page=source_page,
    )


def _stored_page(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text.isdigit() else None


def _norm(name: str) -> str:
    from app.services.agreements.parse import normalize_item_name

    return normalize_item_name(name)
