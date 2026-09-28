from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You extract Indonesian hospital claim invoice data as JSON. "
    "Reply with a single JSON object only. Do not invent numbers."
)

CLASSIFY_HINT = """
Decide if the document is a hospital claim invoice / rincian biaya / tagihan
with billed line items (name, quantity, unit price, total).
Return JSON: {"is_claim_invoice": true|false, "confidence": 0-1, "reason": "short"}.
Not a claim invoice: IKS catalogs (Kelompok + Tarif PKS), tariff master lists,
letters, ID cards, empty templates without real billed rows.
"""

EXTRACT_HINT = """
Extract billed line items only (skip headers, totals, hospital metadata).
Return JSON: {"items":[{"item_name": str, "quantity": number, "tariff": number,
"discounted_cost": number|null}]}.
tariff is the unit price. discounted_cost is the line total after discount.
Use only amounts that appear in the source. quantity defaults to 1.
"""


def llm_available() -> bool:
    return _provider() in {"openai", "ollama"}


def classify_with_llm(text: str, tables_preview: str) -> dict[str, Any] | None:
    prompt = (
        f"{CLASSIFY_HINT}\n\nTEXT:\n{text[: settings.max_chars_for_llm]}\n\n"
        f"TABLES:\n{tables_preview[:8000]}"
    )
    return _chat_json(prompt)


def extract_with_llm(text: str, tables_preview: str) -> dict[str, Any] | None:
    prompt = (
        f"{EXTRACT_HINT}\n\nTEXT:\n{text[: settings.max_chars_for_llm]}\n\n"
        f"TABLES:\n{tables_preview[:8000]}"
    )
    return _chat_json(prompt)


def _provider() -> str:
    value = (settings.llm_provider or "none").strip().lower()
    if value in {"none", "off", "disabled"}:
        return "openai" if settings.openai_api_key else "none"
    return value


def _chat_json(prompt: str) -> dict[str, Any] | None:
    if not llm_available():
        return None
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package is not installed")
        return None

    client, model = _client_and_model()
    if client is None or not model:
        return None
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            timeout=settings.llm_timeout_seconds,
        )
    except Exception:
        logger.exception("LLM request failed")
        return None
    content = (response.choices[0].message.content or "").strip()
    return _parse_json_object(content)


def _client_and_model():
    from openai import OpenAI

    provider = _provider()
    timeout = settings.llm_timeout_seconds
    if provider == "ollama":
        return (
            OpenAI(
                base_url=settings.ollama_base_url,
                api_key="ollama",
                timeout=timeout,
                max_retries=0,
            ),
            settings.ollama_model,
        )
    if provider == "openai" and settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key, timeout=timeout), settings.openai_model
    return None, None


def _parse_json_object(content: str) -> dict[str, Any] | None:
    stripped = content.strip()
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped)
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
