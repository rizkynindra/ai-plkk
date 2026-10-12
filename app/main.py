from __future__ import annotations

import base64
import binascii
import re
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.schemas import (
    AgreementBase64Request,
    AgreementSaveRequest,
    CompareRequest,
    ConvertBase64Request,
    TariffReviewDraft,
)
from app.services.agreements.pages import AGREEMENTS_PAGE, CATALOG_PAGE, COMPARE_PAGE
from app.services.agreements.service import (
    compare_branch_lines,
    draft_from_payload,
    get_branch_catalog,
    list_hospitals,
    preview_pks,
    save_agreement,
)
from app.services.convert import EmptyExtractionError, NotClaimInvoiceError, convert_document
from app.services.ingest.router import UnsupportedDocumentError, guess_filename
from app.services.preview import get_conversion, render_preview_html, store_conversion
from app.services.tarif_review import (
    REVIEW_PAGE,
    export_workbook,
    load_catalog,
    load_draft,
    marks_for_row,
    pdf_index,
    pdf_info,
    render_page_png,
    save_draft,
    store_pdf,
)
from app.web import render_app_page

app = FastAPI(title="EPLKK Claim to Template_Biaya", version="0.1.0")

CLAIM_BODY = """
      <section class="panel">
        <form id="convert-form" action="/preview" method="post" enctype="multipart/form-data">
          <label id="dropzone" class="dropzone" for="file-input">
            <input id="file-input" type="file" name="file" accept=".pdf,.xlsx,.xls,.csv,.docx,.jpg,.jpeg,.png,.webp,.tif,.tiff,.bmp,application/pdf,image/*" required>
            <div>
              <strong>Drop the claim file</strong>
              <span id="file-label">PDF, Excel, Word, CSV, or image</span>
            </div>
          </label>
          <div class="actions">
            <button id="submit-button" class="button" type="submit">Extract billed lines</button>
          </div>
          <p id="status" class="status" role="status"></p>
        </form>
      </section>
"""

UPLOAD_FORM = render_app_page(
    title="Claim invoice — EPLKK",
    heading="Upload claim invoice",
    lede="Extract billed rows into Template_Biaya. Review them before you download.",
    active="claim",
    body=CLAIM_BODY,
    scripts=["/static/nav.js", "/static/upload.js"],
)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return UPLOAD_FORM


@app.get("/agreements", response_class=HTMLResponse)
def agreements_page() -> str:
    return AGREEMENTS_PAGE


@app.get("/catalog", response_class=HTMLResponse)
def catalog_page() -> str:
    return CATALOG_PAGE


@app.get("/compare", response_class=HTMLResponse)
def compare_page() -> str:
    return COMPARE_PAGE


@app.get("/review", response_class=HTMLResponse)
def tariff_review_page() -> str:
    return REVIEW_PAGE


@app.get("/api/tarif-review/emc-alam-sutera")
async def tariff_review_catalog() -> JSONResponse:
    return JSONResponse(await run_in_threadpool(_review_call, load_catalog))


@app.get("/api/tarif-review/emc-alam-sutera/draft")
def tariff_review_draft_get() -> JSONResponse:
    return JSONResponse(_review_call(load_draft))


@app.put("/api/tarif-review/emc-alam-sutera/draft")
def tariff_review_draft_put(body: TariffReviewDraft) -> JSONResponse:
    return JSONResponse(_review_call(save_draft, body))


@app.get("/api/tarif-review/emc-alam-sutera/pdf")
def tariff_review_pdf_info() -> JSONResponse:
    return JSONResponse(pdf_info())


@app.get("/api/tarif-review/emc-alam-sutera/pdf/index")
async def tariff_review_pdf_index() -> JSONResponse:
    payload = await run_in_threadpool(_review_call, pdf_index)
    return JSONResponse(payload)


@app.post("/api/tarif-review/emc-alam-sutera/pdf")
async def tariff_review_pdf_upload(file: UploadFile = File(...)) -> JSONResponse:
    payload = await file.read()
    info = await run_in_threadpool(_review_call, store_pdf, payload, file.filename or "pks.pdf")
    return JSONResponse(info)


@app.get("/api/tarif-review/emc-alam-sutera/pdf/pages/{page_number}")
async def tariff_review_pdf_page(page_number: int) -> Response:
    png = await run_in_threadpool(_review_call, render_page_png, page_number)
    return Response(content=png, media_type="image/png")


@app.get("/api/tarif-review/emc-alam-sutera/pdf/pages/{page_number}/marks")
async def tariff_review_marks(page_number: int, kode: str = Query(...)) -> JSONResponse:
    payload = await run_in_threadpool(_review_call, marks_for_row, page_number, kode)
    return JSONResponse(payload)


@app.get("/api/tarif-review/emc-alam-sutera/export")
def tariff_review_export() -> Response:
    workbook = _review_call(export_workbook)
    return Response(
        content=workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="TARIF_KESEPAKATAN_EMC_ALAM_SUTERA_reviewed.xlsx"'
        },
    )


@app.post("/preview", response_class=HTMLResponse)
async def preview_page(file: UploadFile = File(...)) -> HTMLResponse:
    preview, workbook = await _convert_upload(file)
    conversion_id = store_conversion(preview, workbook)
    return HTMLResponse(render_preview_html(conversion_id, preview))


@app.get("/preview/{conversion_id}", response_class=HTMLResponse)
def preview_by_id(conversion_id: str) -> HTMLResponse:
    stored = get_conversion(conversion_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Preview expired. Convert the file again.")
    preview, _workbook = stored
    return HTMLResponse(render_preview_html(conversion_id, preview))


@app.get("/preview/{conversion_id}/xlsx")
def download_preview_xlsx(conversion_id: str) -> Response:
    stored = get_conversion(conversion_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Preview expired. Convert the file again.")
    preview, workbook = stored
    return Response(
        content=workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="Template_Biaya.xlsx"',
            "X-Written-Count": str(preview.written_count),
        },
    )


@app.post("/api/convert")
async def convert(
    file: UploadFile = File(...),
    download: bool = Query(False),
) -> Response:
    payload = await file.read()
    return await _convert_payload(payload, file.filename or "document", download)


@app.post("/api/convert/base64")
async def convert_base64(body: ConvertBase64Request) -> Response:
    payload = _decode_base64_file(body.docBase64)
    try:
        filename = guess_filename(payload)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    preview, _workbook = await _run_convert(payload, filename)
    result = preview.model_dump()
    result["chId"] = body.chId
    result["reqId"] = body.reqId
    return JSONResponse(result)


@app.post("/api/convert/xlsx")
async def convert_xlsx(file: UploadFile = File(...)) -> Response:
    return await convert(file=file, download=True)


@app.get("/api/hospitals")
def hospitals() -> list[dict]:
    return list_hospitals()


@app.get("/api/hospitals/{branch_id}")
def hospital_catalog(branch_id: int) -> JSONResponse:
    payload = get_branch_catalog(branch_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Branch not found.")
    return JSONResponse(payload)


@app.post("/api/agreements/preview")
async def agreement_preview(file: UploadFile = File(...)) -> JSONResponse:
    payload = await file.read()
    return JSONResponse(await _preview_pks_payload(payload, file.filename or "pks.pdf"))


@app.post("/api/agreements/preview/base64")
async def agreement_preview_base64(body: AgreementBase64Request) -> JSONResponse:
    draft = await _preview_agreement_base64(body)
    draft["chId"] = body.chId
    draft["reqId"] = body.reqId
    return JSONResponse(draft)


@app.post("/api/agreements")
def agreement_save(body: AgreementSaveRequest) -> JSONResponse:
    try:
        result = save_agreement(draft_from_payload(body.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JSONResponse(result)


@app.post("/api/agreements/base64")
async def agreement_save_base64(body: AgreementBase64Request) -> JSONResponse:
    draft = await _preview_agreement_base64(body)
    try:
        result = save_agreement(draft_from_payload(draft))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["chId"] = body.chId
    result["reqId"] = body.reqId
    return JSONResponse(result)


@app.post("/api/compare")
def compare_invoice(body: CompareRequest) -> JSONResponse:
    lines = body.lines
    if body.conversion_id:
        stored = get_conversion(body.conversion_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Preview expired. Convert the file again.")
        lines = stored[0].lines
    if not lines:
        raise HTTPException(status_code=400, detail="Provide lines or conversion_id.")
    result = compare_branch_lines(body.branch_id, lines)
    if result["catalog_size"] == 0:
        raise HTTPException(status_code=404, detail="No PKS catalog stored for this branch.")
    return JSONResponse(result)


def _review_call(fn, *args):
    try:
        return fn(*args)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail="That page is not in this PDF.") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown Kode Master.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _preview_agreement_base64(body: AgreementBase64Request) -> dict:
    payload = _decode_base64_file(body.docBase64)
    filename = body.filename.strip()
    if not filename:
        try:
            filename = guess_filename(payload)
        except UnsupportedDocumentError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
    draft = await _preview_pks_payload(payload, filename)
    return _apply_agreement_overrides(draft, body)


async def _preview_pks_payload(payload: bytes, filename: str) -> dict:
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file.")
    started = time.perf_counter()
    try:
        draft = await run_in_threadpool(preview_pks, payload, filename)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    draft["elapsed_seconds"] = round(time.perf_counter() - started, 1)
    return draft


def _apply_agreement_overrides(draft: dict, body: AgreementBase64Request) -> dict:
    for field in ("group_name", "branch_name", "city", "address", "code", "effective_date"):
        value = getattr(body, field) or ""
        if str(value).strip():
            draft[field] = str(value).strip()
    if body.aliases:
        draft["aliases"] = body.aliases
    if body.filename.strip():
        draft["source_filename"] = body.filename.strip()
    return draft


def _decode_base64_file(value: str) -> bytes:
    text = value.strip()
    if text.startswith("data:") and ";base64," in text:
        text = text.split(";base64,", 1)[1]
    text = re.sub(r"\s+", "", text)
    if not text:
        raise HTTPException(status_code=400, detail="Empty file.")
    try:
        return base64.b64decode(text, validate=True)
    except binascii.Error as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 content.") from exc


async def _convert_payload(payload: bytes, filename: str, download: bool = False) -> Response:
    preview, workbook = await _run_convert(payload, filename)
    if download:
        return Response(
            content=workbook,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": 'attachment; filename="Template_Biaya.xlsx"',
                "X-Written-Count": str(preview.written_count),
            },
        )
    return JSONResponse(preview.model_dump())


async def _convert_upload(file: UploadFile) -> tuple:
    payload = await file.read()
    return await _run_convert(payload, file.filename or "document")


async def _run_convert(payload: bytes, filename: str) -> tuple:
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file.")
    try:
        started = time.perf_counter()
        preview, workbook = await run_in_threadpool(convert_document, payload, filename)
        preview.elapsed_seconds = round(time.perf_counter() - started, 1)
        return preview, workbook
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except NotClaimInvoiceError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc
    except EmptyExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
