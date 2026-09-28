from __future__ import annotations

import re
from typing import Any

_IDR_GROUPED = re.compile(
    r"^(?:rp|idr)?\s*(\d{1,3}(?:\.\d{3})+)(?:[,](\d{1,2}))?$",
    re.IGNORECASE,
)
_PLAIN = re.compile(r"^(?:rp|idr)?\s*(\d+)(?:[.,](\d{1,2}))?$", re.IGNORECASE)
_EMBEDDED_AMOUNT = re.compile(
    r"(?:rp|idr)?\s*\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?",
    re.IGNORECASE,
)


def parse_idr_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none", "-"}:
        return None
    if re.search(r"[A-Za-z]", raw) and not re.match(r"^(rp|idr)\b", raw, re.I):
        return None

    compact = re.sub(r"[\s]", "", raw).rstrip(".-")
    grouped = _IDR_GROUPED.match(compact)
    if grouped:
        whole = grouped.group(1).replace(".", "")
        cents = grouped.group(2) or "0"
        return float(f"{whole}.{cents}")

    plain = _PLAIN.match(compact.replace(",", "."))
    if plain:
        whole = plain.group(1)
        cents = plain.group(2) or "0"
        return float(f"{whole}.{cents}")
    return None


def amounts_in_text(text: str) -> set[float]:
    found: set[float] = set()
    for match in _EMBEDDED_AMOUNT.finditer(text or ""):
        amount = parse_idr_amount(match.group(0))
        if amount is not None:
            found.add(amount)
    return found


def amount_in_source(amount: float, source_amounts: set[float], rel_tol: float = 0.001) -> bool:
    for candidate in source_amounts:
        if abs(candidate - amount) <= max(1.0, abs(amount) * rel_tol):
            return True
    return False
