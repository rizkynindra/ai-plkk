from __future__ import annotations

import base64
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from difflib import SequenceMatcher
from io import BytesIO
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

import pymupdf
from PIL import Image

from app.config import settings
from app.schemas import CostLine
from app.services.money import parse_idr_amount

logger = logging.getLogger(__name__)

VISION_PROMPT = """
Analyze this page image from an Indonesian hospital claim bundle.

A billing page has itemized charge rows: service/drug names with quantity
and unit price and/or line total (DETAIL LAYANAN, TINDAKAN, RUANGAN,
OBAT DAN ALKES, or similar).

NOT a billing page: Kuitansi, cover letters, Tagihan with only one grand
total, identity cards, lab/radiology narratives, forms, and payment receipts.

If this is a billing page, copy every itemized charge row exactly as visible.
Do not summarize, group, or invent rows. Skip headers, patient identity,
subtotals, discounts, grand totals, "Jumlah biaya", "Total Piutang",
"Tagihan ... a.n ...", "Terbilang", and category subtotals whose names are
only "INSTALASI ...". Do extract "Biaya Administrasi" when it is a billed
amount. If the same drug appears on more than one date, keep each row.

Return one JSON object:
{
  "page_type": "short type",
  "is_billing_page": true,
  "reason": "short reason",
  "items": [
    {
      "item_name": "exact visible description",
      "service_date": "YYYY-MM-DD or empty",
      "quantity_text": "exact visible quantity or empty",
      "tariff_text": "exact visible unit price or empty",
      "discounted_cost_text": "exact visible line total or empty",
      "evidence": "the exact visible row text containing these values"
    }
  ]
}
""".strip()

CLASSIFY_PROMPT = """
Look at this Indonesian hospital claim page. Return JSON only:
{"is_billing_page": false, "page_type": "short type", "reason": "short"}

is_billing_page is true only if the page has itemized charge rows: service or
drug names together with quantity and/or unit price or line total
(DETAIL LAYANAN, TINDAKAN, RUANGAN, OBAT DAN ALKES, or a continuation of
those tables). False for kuitansi, identity cards, photos, letters, lab
narratives, forms, and a Tagihan page with only a grand total.
""".strip()

NON_BILLING_HEADER_MARKERS = (
    "kartu peserta",
    "ktp atau",
    "surat kelayakan",
    "ringkasan pulang",
    "foto kondisi",
    "daftar hadir",
    "laporan kasus",
    "bukti pembayaran",
    "keterangan kronologis",
    "kronologis kejadian",
)

_endpoint_lock = threading.Lock()
_endpoint_cursor = 0
# Ignore HTTP_PROXY/HTTPS_PROXY. Corporate proxies on GPU servers often
# intercept 127.0.0.1 and return 403 before the request reaches Ollama.
_ollama_opener = build_opener(ProxyHandler({}))


@dataclass
class VisionPageResult:
    page_number: int
    page_type: str
    is_billing_page: bool
    reason: str
    lines: list[CostLine]


def vision_available() -> bool:
    return settings.vision_enabled and settings.vision_provider == "ollama"


def extract_pdf_cost_lines_with_vision(data: bytes) -> list[CostLine]:
    if not vision_available():
        return []

    document = pymupdf.open(stream=data, filetype="pdf")
    lines: list[CostLine] = []
    try:
        page_count = min(document.page_count, settings.vision_max_pages)
        scan_page_indexes = [
            page_index
            for page_index in range(page_count)
            if _needs_vision(
                document.load_page(page_index).get_text("text").strip(),
                document.load_page(page_index).get_images(full=True),
            )
        ]
        scanned_set = set(scan_page_indexes)
        visited: set[int] = set()
        logger.info("Vision scanning %s pages for a billing seed", len(scan_page_indexes))

        def extract_page(page_index: int) -> bool:
            if page_index in visited or page_index not in scanned_set:
                return False
            page = document.load_page(page_index)
            if looks_like_non_billing_header(page.get_text("text")):
                visited.add(page_index)
                return False
            visited.add(page_index)
            result = analyze_page(page, page_index + 1)
            detail_lines = [line for line in result.lines if not _is_summary_line(line)]
            if not result.is_billing_page or not detail_lines:
                logger.info("Vision extract found no billed lines on PDF page %s", page_index + 1)
                return False
            lines.extend(detail_lines)
            logger.info(
                "Vision found %s billed lines on PDF page %s",
                len(detail_lines),
                result.page_number,
            )
            return True

        def walk_from_seed(seed_index: int) -> None:
            next_index = seed_index + 1
            while extract_page(next_index):
                next_index += 1
            prev_index = seed_index - 1
            while extract_page(prev_index):
                prev_index -= 1

        for seed_index in scan_page_indexes:
            if seed_index in visited:
                continue
            page = document.load_page(seed_index)
            page_text = page.get_text("text")
            if looks_like_non_billing_header(page_text):
                continue
            if not _classify_billing_page(page):
                logger.info("Vision skipped PDF page %s after classify", seed_index + 1)
                continue
            if not extract_page(seed_index):
                continue
            walk_from_seed(seed_index)
            if len(lines) >= settings.vision_min_detail_lines:
                logger.info(
                    "Vision stopped after %s billed lines without scanning remaining pages",
                    len(lines),
                )
                break
    finally:
        document.close()

    lines = _prefer_detail_lines(lines)
    lines.sort(key=lambda line: line.source_page or 0)
    for sequence_no, line in enumerate(lines, start=1):
        line.sequence_no = sequence_no
    return lines


def analyze_page(page: pymupdf.Page, page_number: int) -> VisionPageResult:
    return _analyze_crops(_page_crops(page), page_number)


def extract_image_cost_lines_with_vision(data: bytes) -> list[CostLine]:
    if not vision_available():
        return []
    image = Image.open(BytesIO(data)).convert("RGB")
    result = _analyze_crops(_pil_crops(image), 1)
    for sequence_no, line in enumerate(result.lines, start=1):
        line.sequence_no = sequence_no
    return result.lines


def _analyze_crops(crops: list[bytes], page_number: int) -> VisionPageResult:
    merged: list[CostLine] = []
    seen: set[tuple] = set()
    is_billing_page = False
    page_type = "unknown"
    reason = ""
    worker_count = max(1, min(len(crops), settings.vision_parallel_requests))
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        payloads = list(pool.map(lambda crop: _ollama_vision_json(crop, VISION_PROMPT), crops))
    for payload in payloads:
        if not payload:
            continue
        page_type = str(payload.get("page_type") or page_type)
        reason = str(payload.get("reason") or reason)
        if not bool(payload.get("is_billing_page")):
            continue
        is_billing_page = True
        for line in _validated_lines(payload.get("items"), page_number):
            key = _line_key(line)
            if key in seen:
                continue
            seen.add(key)
            merged.append(line)
    merged = _dedupe_typo_lines(merged)
    return VisionPageResult(page_number, page_type, is_billing_page, reason, merged)


def _needs_vision(text: str, images: list[tuple]) -> bool:
    return len(text) < settings.pdf_scan_text_threshold + 20 and bool(images)


def _render_page(page: pymupdf.Page, scale: float | None = None) -> bytes:
    render_scale = settings.vision_render_scale if scale is None else scale
    matrix = pymupdf.Matrix(render_scale, render_scale)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    return pixmap.tobytes("jpeg", jpg_quality=settings.vision_jpeg_quality)


def _page_crops(page: pymupdf.Page) -> list[bytes]:
    image = Image.open(BytesIO(_render_page(page))).convert("RGB")
    return _pil_crops(image)


def _pil_crops(image: Image.Image) -> list[bytes]:
    full = _jpeg_bytes(image)
    if image.height < image.width * 1.15:
        return [full]
    height = image.height
    bands = (
        (0, int(height * 0.48)),
        (int(height * 0.28), int(height * 0.74)),
        (int(height * 0.52), height),
    )
    return [
        _jpeg_bytes(image.crop((0, top, image.width, bottom)))
        for top, bottom in bands
    ]


def _jpeg_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="JPEG", quality=settings.vision_jpeg_quality)
    return output.getvalue()


def _line_key(line: CostLine) -> tuple:
    return (
        _norm_name(line.item_name),
        line.service_date or "",
        round(line.quantity, 4),
        round(line.tariff, 2),
        round(line.discounted_cost, 2),
    )


def _norm_name(item_name: str) -> str:
    text = (
        item_name.lower()
        .replace("¼", " 1/4 ")
        .replace("½", " 1/2 ")
        .replace("¾", " 3/4 ")
        .replace("/", " ")
    )
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _dedupe_typo_lines(lines: list[CostLine]) -> list[CostLine]:
    kept: list[CostLine] = []
    for line in lines:
        if any(_is_typo_duplicate(line, other) for other in kept):
            continue
        kept.append(line)
    return kept


def _is_typo_duplicate(left: CostLine, right: CostLine) -> bool:
    if left.service_date != right.service_date:
        return False
    if (
        round(left.quantity, 4),
        round(left.tariff, 2),
        round(left.discounted_cost, 2),
    ) != (
        round(right.quantity, 4),
        round(right.tariff, 2),
        round(right.discounted_cost, 2),
    ):
        return False
    extra = set(_norm_name(left.item_name).split()) ^ set(_norm_name(right.item_name).split())
    if any(re.search(r"\d", token) for token in extra):
        return False
    return SequenceMatcher(None, _norm_name(left.item_name), _norm_name(right.item_name)).ratio() >= 0.78


def _is_summary_line(line: CostLine) -> bool:
    return _is_summary_name(line.item_name)


def _is_summary_name(item_name: str) -> bool:
    name = re.sub(r"\s+", " ", item_name).strip().lower()
    summary_markers = (
        "tagihan rawat",
        "kuitansi",
        "jumlah biaya",
        "total piutang",
        "grand total",
        "total jumlah billing",
        "total setelah",
        "sub total",
        "terbilang",
        "a.n ",
    )
    if any(marker in name for marker in summary_markers):
        return True
    if name.startswith("instalasi "):
        return True
    if name.startswith("total ") or name in {"total", "subtotal", "jumlah"}:
        return True
    return False


def looks_like_non_billing_header(text: str) -> bool:
    lowered = re.sub(r"\s+", " ", text).strip().lower()
    return any(marker in lowered for marker in NON_BILLING_HEADER_MARKERS)


def _classify_billing_page(page: pymupdf.Page) -> bool:
    image = _render_page(page, scale=settings.vision_classify_scale)
    payload = _ollama_vision_json(
        image,
        CLASSIFY_PROMPT,
        num_ctx=settings.vision_classify_context_size,
        num_predict=settings.vision_classify_max_output_tokens,
    )
    if not payload:
        return True
    return bool(payload.get("is_billing_page"))


def _vision_endpoints() -> list[str]:
    extra = [
        part.strip()
        for part in settings.vision_worker_urls.split(",")
        if part.strip()
    ]
    return extra or [settings.ollama_base_url]


def _client_chat_endpoint(base_url: str) -> str:
    url = re.sub(r"/v1$", "", base_url.rstrip("/"))
    url = re.sub(r"^(https?://)0\.0\.0\.0(?=[:/]|$)", r"\g<1>127.0.0.1", url)
    url = re.sub(r"^(https?://)\[::\](?=[:/]|$)", r"\g<1>127.0.0.1", url)
    return url + "/api/chat"


def _next_chat_endpoint() -> str:
    global _endpoint_cursor
    urls = _vision_endpoints()
    with _endpoint_lock:
        url = urls[_endpoint_cursor % len(urls)]
        _endpoint_cursor += 1
    return _client_chat_endpoint(url)


def _ollama_vision_json(
    image: bytes,
    prompt: str,
    num_ctx: int | None = None,
    num_predict: int | None = None,
) -> dict[str, Any] | None:
    endpoint = _next_chat_endpoint()
    body = {
        "model": settings.vision_model,
        "stream": False,
        "format": "json",
        "think": False,
        "keep_alive": "10m",
        "options": {
            "temperature": 0,
            "num_ctx": num_ctx or settings.vision_context_size,
            "num_predict": num_predict or settings.vision_max_output_tokens,
        },
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [base64.b64encode(image).decode("ascii")],
            }
        ],
    }
    request = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "ai-eplkk-vision",
        },
        method="POST",
    )
    try:
        with _ollama_opener.open(request, timeout=settings.vision_timeout_seconds) as response:
            result = json.loads(response.read())
    except HTTPError as exc:
        detail = exc.read()[:500].decode("utf-8", errors="replace")
        logger.exception(
            "Qwen3-VL request failed: %s -> HTTP %s %s %s",
            endpoint,
            exc.code,
            exc.reason,
            detail,
        )
        return None
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        logger.exception("Qwen3-VL request failed: %s", endpoint)
        return None

    content = result.get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Qwen3-VL returned invalid JSON")
        return None
    return parsed if isinstance(parsed, dict) else None


def _prefer_detail_lines(lines: list[CostLine]) -> list[CostLine]:
    has_detail = any(
        sum(1 for line in lines if line.source_page == page) >= 8
        for page in {line.source_page for line in lines}
    )
    if not has_detail:
        return lines
    kept: list[CostLine] = []
    for line in lines:
        name = line.item_name.upper().strip()
        if name.startswith("INSTALASI ") and "DETAIL" not in name:
            continue
        kept.append(line)
    return kept or lines


def _validated_lines(items: object, page_number: int) -> list[CostLine]:
    if not isinstance(items, list):
        return []

    lines: list[CostLine] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("item_name") or "").strip()
        quantity_text = str(item.get("quantity_text") or "").strip()
        tariff_text = str(item.get("tariff_text") or "").strip()
        cost_text = str(item.get("discounted_cost_text") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        service_date = _normalize_date(str(item.get("service_date") or ""))

        quantity = parse_idr_amount(quantity_text) or 1.0
        tariff = parse_idr_amount(tariff_text)
        cost = parse_idr_amount(cost_text)
        if not name or (tariff is None and cost is None):
            continue
        if _is_summary_name(name):
            continue
        if not _amount_is_evidenced(tariff_text, evidence):
            tariff = None
        if not _amount_is_evidenced(cost_text, evidence):
            cost = None
        if tariff is None and cost is None:
            continue
        if tariff is None:
            tariff = cost / quantity
        if cost is None:
            cost = quantity * tariff
        tariff, cost = _reconcile_unit_and_total(quantity, tariff, cost)

        lines.append(
            CostLine(
                sequence_no=0,
                item_name=name,
                quantity=quantity,
                tariff=tariff,
                discounted_cost=cost,
                source_page=page_number,
                evidence=evidence,
                service_date=service_date or None,
            )
        )
    return lines


def _reconcile_unit_and_total(quantity: float, tariff: float, cost: float) -> tuple[float, float]:
    if quantity <= 0:
        return tariff, cost
    expected = quantity * tariff
    if abs(expected - cost) <= max(1.0, 0.01 * cost):
        return tariff, cost
    if abs(tariff - cost) <= 1:
        return cost / quantity, cost
    if abs(quantity * cost - tariff) <= max(1.0, 0.01 * tariff):
        return cost, tariff
    return tariff, cost


def _normalize_date(value: str) -> str:
    text = value.strip()
    match = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if not match:
        match = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})", text)
        if match:
            day, month, year = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        return ""
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _amount_is_evidenced(amount_text: str, evidence: str) -> bool:
    if not amount_text:
        return False
    compact_amount = re.sub(r"\s+", "", amount_text).lower()
    compact_evidence = re.sub(r"\s+", "", evidence).lower()
    return compact_amount in compact_evidence
