from __future__ import annotations

from html import escape
from uuid import uuid4

from app.schemas import ConversionPreview
from app.web import render_app_page

_STORE: dict[str, tuple[ConversionPreview, bytes]] = {}


def store_conversion(preview: ConversionPreview, workbook: bytes) -> str:
    conversion_id = uuid4().hex
    _STORE[conversion_id] = (preview, workbook)
    return conversion_id


def get_conversion(conversion_id: str) -> tuple[ConversionPreview, bytes] | None:
    return _STORE.get(conversion_id)


def render_preview_html(conversion_id: str, preview: ConversionPreview) -> str:
    rows = "\n".join(_row_html(line) for line in preview.lines)
    body = f"""
      <div class="facts">
        <div><span>Written</span><strong>{preview.written_count}</strong></div>
        <div><span>Needs review</span><strong>{preview.review_count}</strong></div>
        <div><span>Processing time</span><strong>{_format_elapsed(preview.elapsed_seconds)}</strong></div>
      </div>
      <p class="actions">
        <a class="button" href="/preview/{conversion_id}/xlsx">Download Template_Biaya.xlsx</a>
        <a class="button secondary" href="/">Upload another claim</a>
      </p>
      <section id="preview-compare" class="panel" data-conversion-id="{conversion_id}">
        <label>PKS branch
          <select id="compare-branch">
            <option value="">Select a saved branch</option>
          </select>
        </label>
        <div class="actions">
          <button id="compare-button" class="button" type="button">Compare with PKS</button>
        </div>
        <p id="compare-status" class="status" role="status"></p>
      </section>
      <div class="facts" id="compare-facts" hidden></div>
      <div id="compare-table" class="table-wrap" hidden>
        <table>
          <thead>
            <tr>
              <th>No</th>
              <th>Item Biaya</th>
              <th>Invoice tarif</th>
              <th>Match</th>
              <th>PKS item</th>
              <th>PKS tarif</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody id="compare-body"></tbody>
        </table>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>No</th>
              <th>Item Biaya</th>
              <th>Jumlah</th>
              <th>Tarif</th>
              <th>Biaya</th>
              <th>Page</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
      </div>
"""
    return render_app_page(
        title=f"Preview {preview.filename}",
        heading="Extracted cost lines",
        lede=f"{preview.filename} · {preview.classification.method} — {preview.classification.reason}",
        active="claim",
        body=body,
        scripts=["/static/nav.js", "/static/compare.js"],
    )


def _row_html(line) -> str:
    css = ' class="review"' if line.needs_review else ""
    note = escape(line.review_reason or "")
    page = line.source_page if line.source_page is not None else ""
    return (
        f"<tr{css}><td class='num'>{line.sequence_no}</td>"
        f"<td>{escape(line.item_name)}</td>"
        f"<td class='num'>{_qty(line.quantity)}</td>"
        f"<td class='num'>{_idr(line.tariff)}</td>"
        f"<td class='num'>{_idr(line.discounted_cost)}</td>"
        f"<td class='num'>{page}</td>"
        f"<td>{note}</td></tr>"
    )


def _qty(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def _format_elapsed(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    return f"{minutes} min {rest:.1f} s"


def _idr(value: float) -> str:
    as_int = int(round(value))
    if abs(value - as_int) < 0.001:
        return f"{as_int:,}".replace(",", ".")
    return f"{value:,.2f}"
