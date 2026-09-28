from __future__ import annotations

from rapidfuzz import fuzz

from app.schemas import CostLine
from app.services.agreements.parse import CatalogItem, normalize_item_name

MATCH_THRESHOLD = 88
PRICE_ABS_TOLERANCE = 1.0
PRICE_REL_TOLERANCE = 0.005


def compare_lines(lines: list[CostLine], catalog: list[CatalogItem]) -> list[dict]:
    indexed = [
        (item, normalize_item_name(item.item_name))
        for item in catalog
        if item.tariff is not None
    ]
    results: list[dict] = []
    for line in lines:
        payload = line.model_dump()
        payload.update(_match_line(line, indexed))
        results.append(payload)
    return results


def _match_line(line: CostLine, indexed: list[tuple[CatalogItem, str]]) -> dict:
    query = normalize_item_name(line.item_name)
    if not query or not indexed:
        return _status("unmatched")

    scored: list[tuple[float, CatalogItem]] = []
    for item, normalized in indexed:
        if normalized == query:
            score = 100.0
        else:
            score = float(fuzz.token_set_ratio(query, normalized))
        if score >= MATCH_THRESHOLD:
            scored.append((score, item))
    if not scored:
        return _status("unmatched")
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best_score, best = scored[0]
    if len(scored) > 1 and abs(scored[0][0] - scored[1][0]) < 0.5:
        if normalize_item_name(scored[0][1].item_name) != normalize_item_name(scored[1][1].item_name):
            return _status("ambiguous", best, best_score)

    delta = None if best.tariff is None else round(line.tariff - best.tariff, 2)
    matched = best.tariff is not None and _tariff_close(line.tariff, best.tariff)
    status = "matched" if matched else "price_mismatch"
    return _status(status, best, best_score, delta)


def _tariff_close(left: float, right: float) -> bool:
    return abs(left - right) <= max(PRICE_ABS_TOLERANCE, PRICE_REL_TOLERANCE * max(abs(left), abs(right)))


def _status(
    status: str,
    item: CatalogItem | None = None,
    score: float | None = None,
    delta: float | None = None,
) -> dict:
    reason = None
    needs_review = status != "matched"
    if status == "unmatched":
        reason = "Not found in the branch PKS catalog."
    elif status == "ambiguous":
        reason = "Multiple PKS items match this name."
    elif status == "price_mismatch" and item is not None:
        reason = f"Invoice tarif differs from PKS {item.item_name} ({item.tariff:,.0f})".replace(",", ".")
    return {
        "match_status": status,
        "matched_item_name": item.item_name if item else None,
        "matched_item_code": item.item_code if item else None,
        "agreement_tariff": item.tariff if item else None,
        "tariff_delta": delta,
        "match_score": score,
        "needs_review": needs_review,
        "review_reason": reason,
    }
