from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hospital_groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES hospital_groups(id),
    name TEXT NOT NULL,
    city TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    aliases TEXT NOT NULL DEFAULT '',
    UNIQUE(group_id, name)
);
CREATE TABLE IF NOT EXISTS agreements (
    id INTEGER PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    source_filename TEXT NOT NULL,
    effective_date TEXT NOT NULL DEFAULT '',
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS agreement_items (
    id INTEGER PRIMARY KEY,
    agreement_id INTEGER NOT NULL REFERENCES agreements(id),
    kelompok TEXT NOT NULL DEFAULT '',
    item_code TEXT NOT NULL DEFAULT '',
    item_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    tariff REAL,
    tariff_note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_items_agreement ON agreement_items(agreement_id);
CREATE INDEX IF NOT EXISTS idx_items_norm ON agreement_items(normalized_name);
"""

_connection: sqlite3.Connection | None = None
_connection_path: Path | None = None


def db_path() -> Path:
    path = Path(settings.agreements_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    global _connection, _connection_path
    path = db_path()
    if _connection is None or _connection_path != path:
        if _connection is not None:
            _connection.close()
        _connection = sqlite3.connect(path, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.executescript(_SCHEMA)
        _connection_path = path
    return _connection


def reset_connection() -> None:
    global _connection, _connection_path
    if _connection is not None:
        _connection.close()
    _connection = None
    _connection_path = None
