from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

NAVY = RGBColor(0x1B, 0x3A, 0x4B)
TEAL = RGBColor(0x2A, 0x6F, 0x7F)
INK = RGBColor(0x1F, 0x29, 0x33)
MUTED = RGBColor(0x5B, 0x64, 0x6E)
RULE = RGBColor(0xC8, 0xBE, 0xB0)
PAPER = RGBColor(0xF7, 0xF4, 0xEE)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
AMBER = RGBColor(0xB8, 0x86, 0x0B)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
OUT = Path(__file__).resolve().parents[1] / "docs" / "EPLKK-project-overview.pptx"
OUT_ID = Path(__file__).resolve().parents[1] / "docs" / "EPLKK-project-overview-id.pptx"


def _set_run(run, text: str, size: int, color: RGBColor, bold: bool = False) -> None:
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.name = "Calibri"


def add_text(slide, left, top, width, height, lines, *, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT, spacing=8):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for index, line in enumerate(lines):
        p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(spacing)
        run = p.add_run()
        _set_run(run, line, size, color, bold)
    return box


def add_bullets(slide, left, top, width, height, items, *, size=17, color=INK):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for index, item in enumerate(items):
        p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = Pt(8)
        run = p.add_run()
        _set_run(run, item, size, color)
    return box


def fill_slide(slide, color=PAPER):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def bar(slide, left, top, width, height, color):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def footer(slide, page: int, total: int):
    add_text(slide, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — claim extract, PKS store, compare"], size=11, color=MUTED)
    add_text(slide, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"{page} / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)


def title_block(slide, kicker: str, title: str):
    bar(slide, Inches(0), Inches(0), Inches(0.18), SLIDE_H, TEAL)
    add_text(slide, Inches(0.55), Inches(0.28), Inches(12), Inches(0.3), [kicker.upper()], size=12, color=TEAL, bold=True)
    add_text(slide, Inches(0.55), Inches(0.52), Inches(12.2), Inches(0.55), [title], size=30, color=NAVY, bold=True)
    bar(slide, Inches(0.55), Inches(1.12), Inches(2.2), Inches(0.04), AMBER)


def card(slide, left, top, width, height, heading, body, kicker=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = WHITE
    shape.line.color.rgb = RULE
    if kicker:
        add_text(slide, left + Inches(0.22), top + Inches(0.14), width - Inches(0.4), Inches(0.25), [kicker], size=11, color=TEAL, bold=True)
        add_text(slide, left + Inches(0.22), top + Inches(0.38), width - Inches(0.4), Inches(0.35), [heading], size=16, color=NAVY, bold=True)
        add_text(slide, left + Inches(0.22), top + Inches(0.78), width - Inches(0.4), height - Inches(0.95), [body], size=13, color=INK)
    else:
        add_text(slide, left + Inches(0.22), top + Inches(0.18), width - Inches(0.4), Inches(0.4), [heading], size=16, color=NAVY, bold=True)
        add_text(slide, left + Inches(0.22), top + Inches(0.58), width - Inches(0.4), height - Inches(0.75), [body], size=13, color=INK)


def build() -> Path:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]
    total = 14

    # 1 title
    s = prs.slides.add_slide(blank)
    fill_slide(s, NAVY)
    bar(s, Inches(0), Inches(0), Inches(0.22), SLIDE_H, TEAL)
    add_text(s, Inches(0.8), Inches(2.0), Inches(11.5), Inches(0.35), ["INTERNAL BRIEFING"], size=13, color=AMBER, bold=True)
    add_text(s, Inches(0.8), Inches(2.4), Inches(11.5), Inches(1.4), ["How EPLKK reads a hospital claim and checks it against a branch PKS"], size=34, color=WHITE, bold=True)
    add_text(
        s,
        Inches(0.8),
        Inches(4.1),
        Inches(11),
        Inches(0.9),
        ["Local FastAPI service. Copies billed rows as written. Does not remap them onto the IKS catalog."],
        size=18,
        color=RGBColor(0xD5, 0xDE, 0xE3),
    )
    add_text(s, Inches(0.8), Inches(6.6), Inches(11), Inches(0.3), ["Stack: FastAPI · Qwen3-VL 8B-instruct (Ollama) · rapidfuzz · SQLite"], size=14, color=RGBColor(0xA8, 0xBE, 0xC4))

    # 2 problem
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Context", "What the service is for")
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.45),
        Inches(12.2),
        Inches(5.2),
        [
            "EPLKK claim files arrive as digital Excel/PDF or as a scanned gabungan bundle (dozens of pages).",
            "Finance still needs Template_Biaya: No, Item Biaya, Jumlah, Tarif, Biaya — copied from the invoice, not rewritten.",
            "Each hospital branch has its own PKS / tarif book. A billed name may match, differ in price, or not exist.",
            "Posting a tarif book or Daftar_Biaya_IKS to convert is rejected (422). That file goes to Upload PKS.",
        ],
    )
    footer(s, 2, total)

    # 3 three jobs
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Product", "Three jobs, not one model")
    card(s, Inches(0.55), Inches(1.45), Inches(3.9), Inches(4.8), "1. Extract claim", "Parse tables first. If the PDF is a scan, Qwen3-VL reads page images and returns itemized rows. Output is Template_Biaya plus JSON lines.", kicker="CLAIM INVOICE")
    card(s, Inches(4.7), Inches(1.45), Inches(3.9), Inches(4.8), "2. Store PKS", "Read a tarif book (text layer first). Edit rumah sakit / branch, then save CODE + name + tarif in SQLite per branch.", kicker="UPLOAD PKS")
    card(s, Inches(8.85), Inches(1.45), Inches(3.9), Inches(4.8), "3. Compare", "Keep invoice wording. Flag matched, price_mismatch, unmatched, or ambiguous against that branch catalog.", kicker="COMPARE")
    footer(s, 3, total)

    # 4 extract pipeline
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Extract", "How a claim becomes Template_Biaya")
    steps = [
        ("Ingest", "PDF, xlsx, xls, csv, docx, or image. Type from the filename or from file bytes on the base64 API."),
        ("Tables first", "pdfplumber / openpyxl / python-docx. Digital invoices never call the vision model."),
        ("Vision fallback", "Empty table + image-heavy PDF → Qwen3-VL classify, then 3 overlapping crops on billing pages."),
        ("Clean rows", "Skip kuitansi grand totals and INSTALASI rollups. Keep Biaya Administrasi. Amounts must appear in the visible row."),
        ("Write Excel", "Fill the official Template_Biaya shell. Preview is held in memory until the process restarts."),
    ]
    top = 1.4
    for title, body in steps:
        add_text(s, Inches(0.55), Inches(top), Inches(2.4), Inches(0.7), [title], size=16, color=TEAL, bold=True)
        add_text(s, Inches(3.1), Inches(top), Inches(9.5), Inches(0.85), [body], size=16, color=INK)
        top += 0.95
    footer(s, 4, total)

    # 5 pks compare
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "PKS", "How a tarif book is stored and compared")
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.4),
        Inches(12.2),
        Inches(5.3),
        [
            "TARIF PELNI.pdf-style books: parse CODE + name + tarif from the text layer. Vision only if a page is image-only.",
            "Save is per hospital group + branch name. Same branch name updates; a new name (Jakarta vs Malang) is a new catalog.",
            "Compare uses rapidfuzz token_set_ratio on normalized names (threshold 88). Not embeddings, not a vector database.",
            "If the name hits and tarif is within Rp 1 or 0.5%, status is matched. Same name, different tarif → price_mismatch.",
            "Invoice names are never rewritten to the PKS label. Unmatched is common when obat/tindakan wording differs from CODE labels.",
        ],
    )
    footer(s, 5, total)

    # 6 architecture
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Architecture", "What runs where")
    card(s, Inches(0.55), Inches(1.4), Inches(6.1), Inches(5.1), "Application (CPU)", "FastAPI + uvicorn. Ingest: PyMuPDF, pdfplumber, openpyxl, python-docx, Pillow. Pydantic settings from .env. SQLite at data/agreements.db. Optional FastAPI process via systemd so it survives a closed terminal.", kicker="PYTHON 3.12")
    card(s, Inches(6.9), Inches(1.4), Inches(5.85), Inches(5.1), "Vision runtime (GPU)", "Ollama on localhost:11434 serves qwen3-vl:8b-instruct. The app POSTs JPEG page crops to /api/chat and asks for JSON rows. One 24 GB card (L4 / 3090-class) is enough at 32K context.", kicker="OLLAMA")
    footer(s, 6, total)

    # 7 model
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Model", "The only neural net in the convert path")
    add_text(s, Inches(0.55), Inches(1.4), Inches(12.2), Inches(0.45), ["Qwen3-VL 8B-instruct  —  vision-language model, served locally by Ollama"], size=20, color=NAVY, bold=True)
    add_bullets(
        s,
        Inches(0.55),
        Inches(2.0),
        Inches(12.2),
        Inches(4.6),
        [
            "Family: Qwen3-VL (Alibaba). 8B instruct weights, not the thinking tag qwen3-vl:8b.",
            "It is a pretrained multimodal LLM: image tokens + text in, JSON out. We did not train or fine-tune a detector.",
            "Job 1 — classify: is this page itemized billing, or kuitansi / KTP / letter?",
            "Job 2 — extract: copy every charge row (name, qty, unit price, line total, evidence text).",
            "Digital files skip this model entirely. LLM_PROVIDER=none; the text LLM (qwen3.5 / OpenAI) is unused on convert.",
            "Tesseract exists only as an image OCR fallback. Scanned gabungan PDFs use Qwen3-VL, not Tesseract.",
        ],
    )
    footer(s, 7, total)

    # 8 why
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Why this stack", "Reasons, not slogans")
    rows = [
        ("Qwen3-VL 8B-instruct", "Reads Indonesian billing tables from photos. 8B fits one 24 GB GPU at 32K context. Instruct tag returns JSON; thinking tag is slower and often empty."),
        ("Ollama, not a cloud VL API", "Claim PDFs contain patient billing. Inference stays on the L4 box. Same /api/chat interface for classify and extract."),
        ("Tables before vision", "A digital xlsx/pdf is milliseconds and deterministic. A 74-page scan is minutes and only runs when text extract is empty."),
        ("rapidfuzz, not embeddings", "PKS matching is short Indonesian item names vs a few thousand catalog rows. Token-set ratio is enough; a vector DB adds ops with little gain."),
        ("SQLite per branch", "One file, no extra service. Latest agreement for a branch is what compare reads."),
        ("No custom CNN / YOLO", "Pages are not a fixed form. A general VL model plus JSON schema is cheaper to maintain than a labeled detection dataset."),
    ]
    top = 1.35
    for name, why in rows:
        add_text(s, Inches(0.55), Inches(top), Inches(3.5), Inches(0.75), [name], size=14, color=TEAL, bold=True)
        add_text(s, Inches(4.2), Inches(top), Inches(8.5), Inches(0.8), [why], size=14, color=INK)
        top += 0.82
    footer(s, 8, total)

    # 9 what we don't use
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Scope", "What this project is not")
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.45),
        Inches(12.2),
        Inches(5.2),
        [
            "Not an IKS mapper. Convert never rewrites billed items onto Daftar_Biaya_IKS.",
            "Not a hosted LLM product. OpenAI keys are optional leftovers; convert does not call them.",
            "Not a trained in-house vision network. No fine-tune, no GPU training loop.",
            "Not OCR-first. Tesseract is fallback only.",
            "Not a durable claim store. Preview IDs die when uvicorn restarts. PKS rows in SQLite do persist.",
        ],
    )
    footer(s, 9, total)

    # 10 UI
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "UI", "Four screens")
    card(s, Inches(0.55), Inches(1.45), Inches(5.9), Inches(2.3), "Claim invoice  /", "Drop a claim → Extract billed lines → check the table → Download Template_Biaya.xlsx. Optional Compare with PKS on the same preview.")
    card(s, Inches(6.7), Inches(1.45), Inches(5.9), Inches(2.3), "Upload PKS  /agreements", "Drop TARIF PELNI.pdf (or xlsx). Edit hospital / branch / city. Save branch catalog.")
    card(s, Inches(0.55), Inches(4.0), Inches(5.9), Inches(2.3), "PKS data  /catalog", "Pick a branch and scroll CODE, name, tarif from the latest saved book.")
    card(s, Inches(6.7), Inches(4.0), Inches(5.9), Inches(2.3), "Compare  /compare", "Pick a branch, drop a claim, extract and flag. Counts: matched / price differs / unmatched.")
    footer(s, 10, total)

    # 11 API map
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "API", "Endpoints you actually call")
    add_text(s, Inches(0.55), Inches(1.35), Inches(12), Inches(0.35), ["Base URL example: http://172.28.200.176:8000    ·    JSON clients use the base64 routes"], size=15, color=MUTED)
    pairs = [
        ("POST /api/convert/base64", "Claim file in docBase64 → billed lines JSON. Echoes chId, reqId."),
        ("POST /api/convert", "Same extract, multipart field file. /xlsx or ?download=true returns the workbook."),
        ("POST /api/agreements/base64", "PKS file in docBase64 → parse + save SQLite. Optional filename, branch_name."),
        ("POST /api/agreements/preview/base64", "Same body, no DB write. Then POST the draft to /api/agreements if you need to edit."),
        ("GET /api/hospitals", "Branches. GET /api/hospitals/{branch_id} adds items[]."),
        ("POST /api/compare", "JSON {branch_id, lines} from convert. Or {branch_id, conversion_id} from /preview."),
    ]
    top = 1.8
    for path, meaning in pairs:
        add_text(s, Inches(0.55), Inches(top), Inches(4.8), Inches(0.7), [path], size=14, color=TEAL, bold=True)
        add_text(s, Inches(5.5), Inches(top), Inches(7.3), Inches(0.7), [meaning], size=14, color=INK)
        top += 0.75
    footer(s, 11, total)

    # 12 convert guide
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "API guide", "1 — Convert a claim (Postman)")
    add_text(s, Inches(0.55), Inches(1.35), Inches(12.2), Inches(0.7), ["POST http://<server>:8000/api/convert/base64    Header: Content-Type: application/json"], size=16, color=INK)
    add_text(
        s,
        Inches(0.55),
        Inches(2.05),
        Inches(12.2),
        Inches(2.2),
        [
            '{  "chId": "CH-001",  "reqId": "REQ-001",  "docBase64": "<one-line base64>"  }',
        ],
        size=16,
        color=NAVY,
        bold=True,
    )
    add_bullets(
        s,
        Inches(0.55),
        Inches(3.2),
        Inches(12.2),
        Inches(3.4),
        [
            "Encode with no wraps: macOS  base64 -b 0 -i claim.pdf | pbcopy    Linux  base64 -w0 claim.pdf",
            "Default base64 inserts a newline every 76 chars. That is invalid JSON (control character) → 422 json_invalid.",
            "No filename field. Type is guessed from bytes (%PDF, xlsx ZIP, JPEG, …).",
            "Smoke test: Template_Biaya_sample.xlsx → written_count 2 (BIAYA ADMINISTRASI, HOMECARE).",
            "Gabungan scan: KL26050404910135_gabung.pdf → 74 rows, needs GPU + Ollama, a few minutes.",
        ],
    )
    footer(s, 12, total)

    # 13 pks + compare guide
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "API guide", "2 — Save PKS, then compare")
    add_text(s, Inches(0.55), Inches(1.35), Inches(12.2), Inches(0.35), ["Do not POST a tarif book to /api/convert. That returns 422."], size=16, color=INK, bold=True)
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.85),
        Inches(12.2),
        Inches(4.8),
        [
            "Save: POST /api/agreements/base64  with chId, reqId, docBase64, and filename \"TARIF PELNI.pdf\". Optional branch_name override.",
            "Or two-step: POST /api/agreements/preview (multipart file) → edit JSON → POST /api/agreements.",
            "List: GET /api/hospitals  then  GET /api/hospitals/{branch_id}.",
            "Compare: take .lines from convert JSON, POST /api/compare  { \"branch_id\": 1, \"lines\": [...] }.",
            "conversion_id only works for POST /preview in the same process. /api/convert does not store an id.",
            "Expect matched on ADMINISTRASI RAWAT JALAN BARU @ 75.000 vs TARIF PELNI. HOMECARE vs that book is unmatched.",
        ],
    )
    footer(s, 13, total)

    # 14 errors + run
    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Ops", "Status codes and how to run")
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.4),
        Inches(12.2),
        Inches(3.4),
        [
            "400  empty file or invalid / wrapped-badly base64 that still cannot parse.",
            "404  unknown branch_id, or preview conversion_id gone after restart.",
            "415  unsupported type.",
            "422  not a claim (IKS xlsx, TARIF book on convert), no billed lines, or (old server) FastAPI JSON validation.",
            "OLLAMA_BASE_URL must be http://127.0.0.1:11434/v1 on the GPU box — not 0.0.0.0 (that 403s Host checks).",
            "Run: uvicorn app.main:app --host 0.0.0.0 --port 8000 from the repo root. Or systemd unit deploy/ai-eplkk.service.",
        ],
    )
    add_text(
        s,
        Inches(0.55),
        Inches(5.5),
        Inches(12.2),
        Inches(1.2),
        ["Quality gate used in tests: gabungan sample → 74 itemized rows, Rp 23.559.342. Pytest does not call Ollama."],
        size=16,
        color=NAVY,
        bold=True,
    )
    footer(s, 14, total)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    return OUT


def build_id() -> Path:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]
    total = 14

    s = prs.slides.add_slide(blank)
    fill_slide(s, NAVY)
    bar(s, Inches(0), Inches(0), Inches(0.22), SLIDE_H, TEAL)
    add_text(s, Inches(0.8), Inches(2.0), Inches(11.5), Inches(0.35), ["BRIEFING INTERNAL"], size=13, color=AMBER, bold=True)
    add_text(s, Inches(0.8), Inches(2.4), Inches(11.5), Inches(1.5), ["Cara EPLKK membaca klaim rumah sakit dan membandingkannya dengan PKS cabang"], size=32, color=WHITE, bold=True)
    add_text(
        s,
        Inches(0.8),
        Inches(4.2),
        Inches(11),
        Inches(0.9),
        ["Layanan FastAPI lokal. Menyalin baris tagihan apa adanya. Tidak memetakan ulang ke katalog IKS."],
        size=18,
        color=RGBColor(0xD5, 0xDE, 0xE3),
    )
    add_text(s, Inches(0.8), Inches(6.6), Inches(11), Inches(0.3), ["Stack: FastAPI · Qwen3-VL 8B-instruct (Ollama) · rapidfuzz · SQLite"], size=14, color=RGBColor(0xA8, 0xBE, 0xC4))

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Konteks", "Untuk apa layanan ini")
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.45),
        Inches(12.2),
        Inches(5.2),
        [
            "Berkas klaim EPLKK datang sebagai Excel/PDF digital atau gabungan hasil scan (puluhan halaman).",
            "Keuangan tetap butuh Template_Biaya: No, Item Biaya, Jumlah, Tarif, Biaya — disalin dari tagihan, bukan ditulis ulang.",
            "Setiap cabang rumah sakit punya buku tarif / PKS sendiri. Nama item bisa cocok, beda harga, atau tidak ada.",
            "Mengirim buku tarif atau Daftar_Biaya_IKS ke convert ditolak (422). Berkas itu masuk lewat Unggah PKS.",
        ],
    )
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"2 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Produk", "Tiga pekerjaan, bukan satu model")
    card(s, Inches(0.55), Inches(1.45), Inches(3.9), Inches(4.8), "1. Ekstrak klaim", "Tabel digital dibaca dulu. Jika PDF hasil scan, Qwen3-VL membaca gambar halaman dan mengembalikan baris rincian. Keluaran: Template_Biaya plus JSON.", kicker="KLAIM")
    card(s, Inches(4.7), Inches(1.45), Inches(3.9), Inches(4.8), "2. Simpan PKS", "Baca buku tarif (lapisan teks dulu). Sunting nama RS / cabang, lalu simpan CODE + nama + tarif di SQLite per cabang.", kicker="UNGGAH PKS")
    card(s, Inches(8.85), Inches(1.45), Inches(3.9), Inches(4.8), "3. Bandingkan", "Tulisan di tagihan tidak diubah. Tandai matched, price_mismatch, unmatched, atau ambiguous terhadap katalog cabang itu.", kicker="COMPARE")
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"3 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Ekstrak", "Dari klaim ke Template_Biaya")
    steps = [
        ("Ingest", "PDF, xlsx, xls, csv, docx, atau gambar. Jenis file dari nama, atau dari byte pada API base64."),
        ("Tabel dulu", "pdfplumber / openpyxl / python-docx. Tagihan digital tidak memanggil model vision."),
        ("Cadangan vision", "Tabel kosong + PDF penuh gambar → Qwen3-VL mengklasifikasi, lalu 3 potongan tumpang-tindih pada halaman billing."),
        ("Bersihkan baris", "Lewati total kuitansi dan rekap INSTALASI. Biaya Administrasi tetap diambil. Angka harus tampak di baris bukti."),
        ("Tulis Excel", "Isi cangkang Template_Biaya resmi. Pratinjau hanya di memori sampai proses di-restart."),
    ]
    top = 1.4
    for title, body in steps:
        add_text(s, Inches(0.55), Inches(top), Inches(2.4), Inches(0.7), [title], size=16, color=TEAL, bold=True)
        add_text(s, Inches(3.1), Inches(top), Inches(9.5), Inches(0.85), [body], size=16, color=INK)
        top += 0.95
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"4 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "PKS", "Cara buku tarif disimpan dan dibandingkan")
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.4),
        Inches(12.2),
        Inches(5.3),
        [
            "Buku seperti TARIF PELNI.pdf: CODE + nama + tarif dari lapisan teks. Vision hanya jika halaman murni gambar.",
            "Simpan per grup rumah sakit + nama cabang. Nama cabang sama = pembaruan; nama baru (Jakarta vs Malang) = katalog baru.",
            "Compare memakai rapidfuzz token_set_ratio pada nama yang dinormalisasi (ambang 88). Bukan embedding, bukan vector database.",
            "Nama ketemu dan tarif selisih ≤ Rp 1 atau 0,5% → matched. Nama sama, tarif beda → price_mismatch.",
            "Nama di tagihan tidak pernah diganti ke label PKS. Unmatched wajar jika obat/tindakan beda bunyi dengan label CODE.",
        ],
    )
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"5 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Arsitektur", "Apa yang jalan di mana")
    card(s, Inches(0.55), Inches(1.4), Inches(6.1), Inches(5.1), "Aplikasi (CPU)", "FastAPI + uvicorn. Ingest: PyMuPDF, pdfplumber, openpyxl, python-docx, Pillow. Pengaturan Pydantic dari .env. SQLite di data/agreements.db. Opsional systemd agar tetap hidup setelah terminal ditutup.", kicker="PYTHON 3.12")
    card(s, Inches(6.9), Inches(1.4), Inches(5.85), Inches(5.1), "Runtime vision (GPU)", "Ollama di localhost:11434 menyajikan qwen3-vl:8b-instruct. Aplikasi mengirim potongan JPEG ke /api/chat dan minta baris JSON. Satu kartu 24 GB (L4 / kelas 3090) cukup pada konteks 32K.", kicker="OLLAMA")
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"6 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Model", "Satu-satunya jaring saraf di jalur convert")
    add_text(s, Inches(0.55), Inches(1.4), Inches(12.2), Inches(0.45), ["Qwen3-VL 8B-instruct  —  model vision-language, dijalankan lokal lewat Ollama"], size=20, color=NAVY, bold=True)
    add_bullets(
        s,
        Inches(0.55),
        Inches(2.0),
        Inches(12.2),
        Inches(4.6),
        [
            "Keluarga: Qwen3-VL (Alibaba). Bobot 8B instruct, bukan tag thinking qwen3-vl:8b.",
            "Ini LLM multimodal yang sudah dilatih: token gambar + teks masuk, JSON keluar. Kami tidak melatih atau fine-tune detektor.",
            "Tugas 1 — klasifikasi: halaman ini rincian tagihan, atau kuitansi / KTP / surat?",
            "Tugas 2 — ekstrak: salin setiap baris biaya (nama, qty, harga satuan, jumlah baris, teks bukti).",
            "Berkas digital melewati model ini. LLM_PROVIDER=none; LLM teks (qwen3.5 / OpenAI) tidak dipakai di convert.",
            "Tesseract hanya cadangan OCR gambar. PDF gabungan hasil scan memakai Qwen3-VL, bukan Tesseract.",
        ],
    )
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"7 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Alasan stack", "Alasan teknis, bukan slogan")
    rows = [
        ("Qwen3-VL 8B-instruct", "Membaca tabel billing berbahasa Indonesia dari foto. 8B muat di satu GPU 24 GB pada konteks 32K. Tag instruct mengembalikan JSON; tag thinking lebih lambat dan sering kosong."),
        ("Ollama, bukan API VL cloud", "PDF klaim berisi data tagihan pasien. Inferensi tetap di mesin L4. Antarmuka /api/chat yang sama untuk klasifikasi dan ekstrak."),
        ("Tabel sebelum vision", "xlsx/pdf digital selesai dalam milidetik dan deterministik. Scan 74 halaman butuh menit, dan hanya jalan jika ekstrak teks kosong."),
        ("rapidfuzz, bukan embedding", "Pencocokan PKS: nama item pendek vs ribuan baris katalog. Token-set ratio cukup; vector DB menambah operasi tanpa banyak manfaat."),
        ("SQLite per cabang", "Satu berkas, tanpa layanan tambahan. Compare membaca perjanjian terbaru untuk cabang itu."),
        ("Tanpa CNN / YOLO sendiri", "Halaman bukan formulir tetap. Model VL umum plus skema JSON lebih murah dirawat daripada dataset deteksi berlabel."),
    ]
    top = 1.35
    for name, why in rows:
        add_text(s, Inches(0.55), Inches(top), Inches(3.5), Inches(0.75), [name], size=14, color=TEAL, bold=True)
        add_text(s, Inches(4.2), Inches(top), Inches(8.5), Inches(0.8), [why], size=14, color=INK)
        top += 0.82
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"8 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Lingkup", "Yang bukan pekerjaan proyek ini")
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.45),
        Inches(12.2),
        Inches(5.2),
        [
            "Bukan pemeta IKS. Convert tidak pernah menulis ulang item tagihan ke Daftar_Biaya_IKS.",
            "Bukan produk LLM hosted. Kunci OpenAI opsional dan sisa lama; convert tidak memanggilnya.",
            "Bukan jaring vision yang dilatih sendiri. Tidak ada fine-tune, tidak ada loop pelatihan GPU.",
            "Bukan OCR-first. Tesseract hanya cadangan.",
            "Bukan penyimpan klaim permanen. ID pratinjau hilang saat uvicorn restart. Baris PKS di SQLite tetap ada.",
        ],
    )
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"9 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Antarmuka", "Empat layar")
    card(s, Inches(0.55), Inches(1.45), Inches(5.9), Inches(2.3), "Klaim  /", "Letakkan klaim → Ekstrak baris tagihan → cek tabel → Unduh Template_Biaya.xlsx. Opsional Bandingkan dengan PKS di pratinjau yang sama.")
    card(s, Inches(6.7), Inches(1.45), Inches(5.9), Inches(2.3), "Unggah PKS  /agreements", "Letakkan TARIF PELNI.pdf (atau xlsx). Sunting RS / cabang / kota. Simpan katalog cabang.")
    card(s, Inches(0.55), Inches(4.0), Inches(5.9), Inches(2.3), "Data PKS  /catalog", "Pilih cabang, gulir CODE, nama, tarif dari buku terbaru yang tersimpan.")
    card(s, Inches(6.7), Inches(4.0), Inches(5.9), Inches(2.3), "Compare  /compare", "Pilih cabang, letakkan klaim, ekstrak dan tandai. Hitungan: cocok / beda tarif / tidak ketemu.")
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"10 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "API", "Endpoint yang dipakai klien")
    add_text(s, Inches(0.55), Inches(1.35), Inches(12), Inches(0.35), ["Contoh base URL: http://172.28.200.176:8000    ·    klien JSON memakai rute base64"], size=15, color=MUTED)
    pairs = [
        ("POST /api/convert/base64", "Berkas klaim di docBase64 → JSON baris tagihan. chId dan reqId dikembalikan."),
        ("POST /api/convert", "Ekstrak yang sama, field multipart file. /xlsx atau ?download=true mengembalikan workbook."),
        ("POST /api/agreements/base64", "Berkas PKS di docBase64 → parse + simpan SQLite. Opsional filename, branch_name."),
        ("POST /api/agreements/preview/base64", "Body sama, tanpa tulis DB. Lalu POST draf ke /api/agreements jika perlu disunting."),
        ("GET /api/hospitals", "Daftar cabang. GET /api/hospitals/{branch_id} menambah items[]."),
        ("POST /api/compare", "JSON {branch_id, lines} dari convert. Atau {branch_id, conversion_id} dari /preview."),
    ]
    top = 1.8
    for path, meaning in pairs:
        add_text(s, Inches(0.55), Inches(top), Inches(4.8), Inches(0.7), [path], size=14, color=TEAL, bold=True)
        add_text(s, Inches(5.5), Inches(top), Inches(7.3), Inches(0.7), [meaning], size=14, color=INK)
        top += 0.75
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"11 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Panduan API", "1 — Convert klaim (Postman)")
    add_text(s, Inches(0.55), Inches(1.35), Inches(12.2), Inches(0.7), ["POST http://<server>:8000/api/convert/base64    Header: Content-Type: application/json"], size=16, color=INK)
    add_text(
        s,
        Inches(0.55),
        Inches(2.05),
        Inches(12.2),
        Inches(2.2),
        [
            '{  "chId": "CH-001",  "reqId": "REQ-001",  "docBase64": "<base64 satu baris>"  }',
        ],
        size=16,
        color=NAVY,
        bold=True,
    )
    add_bullets(
        s,
        Inches(0.55),
        Inches(3.2),
        Inches(12.2),
        Inches(3.4),
        [
            "Encode tanpa potong baris: macOS  base64 -b 0 -i klaim.pdf | pbcopy    Linux  base64 -w0 klaim.pdf",
            "base64 bawaan menyisipkan newline tiap 76 karakter. Itu JSON tidak valid (control character) → 422 json_invalid.",
            "Tidak ada field filename. Jenis file ditebak dari byte (%PDF, ZIP xlsx, JPEG, …).",
            "Uji cepat: Template_Biaya_sample.xlsx → written_count 2 (BIAYA ADMINISTRASI, HOMECARE).",
            "Scan gabungan: KL26050404910135_gabung.pdf → 74 baris, butuh GPU + Ollama, beberapa menit.",
        ],
    )
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"12 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Panduan API", "2 — Simpan PKS, lalu bandingkan")
    add_text(s, Inches(0.55), Inches(1.35), Inches(12.2), Inches(0.35), ["Jangan POST buku tarif ke /api/convert. Itu mengembalikan 422."], size=16, color=INK, bold=True)
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.85),
        Inches(12.2),
        Inches(4.8),
        [
            "Simpan: POST /api/agreements/base64  dengan chId, reqId, docBase64, dan filename \"TARIF PELNI.pdf\". branch_name opsional.",
            "Atau dua langkah: POST /api/agreements/preview (multipart file) → sunting JSON → POST /api/agreements.",
            "Daftar: GET /api/hospitals  lalu  GET /api/hospitals/{branch_id}.",
            "Compare: ambil .lines dari JSON convert, POST /api/compare  { \"branch_id\": 1, \"lines\": [...] }.",
            "conversion_id hanya berlaku untuk POST /preview di proses yang sama. /api/convert tidak menyimpan id.",
            "ADMINISTRASI RAWAT JALAN BARU @ 75.000 vs TARIF PELNI → matched. HOMECARE vs buku itu → unmatched.",
        ],
    )
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"13 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    s = prs.slides.add_slide(blank)
    fill_slide(s)
    title_block(s, "Operasi", "Kode status dan cara menjalankan")
    add_bullets(
        s,
        Inches(0.55),
        Inches(1.4),
        Inches(12.2),
        Inches(3.4),
        [
            "400  berkas kosong, atau base64 rusak / terbungkus newline sehingga JSON tidak bisa dibaca.",
            "404  branch_id tidak ada, atau conversion_id pratinjau hilang setelah restart.",
            "415  jenis berkas tidak didukung.",
            "422  bukan klaim (xlsx IKS, buku TARIF di convert), tidak ada baris tagihan, atau validasi JSON FastAPI.",
            "OLLAMA_BASE_URL di mesin GPU harus http://127.0.0.1:11434/v1 — bukan 0.0.0.0 (itu memicu 403 Host).",
            "Jalankan: uvicorn app.main:app --host 0.0.0.0 --port 8000 dari akar repositori. Atau unit systemd deploy/ai-eplkk.service.",
        ],
    )
    add_text(
        s,
        Inches(0.55),
        Inches(5.5),
        Inches(12.2),
        Inches(1.2),
        ["Baku mutu uji: sampel gabungan → 74 baris rincian, Rp 23.559.342. Pytest tidak memanggil Ollama."],
        size=16,
        color=NAVY,
        bold=True,
    )
    add_text(s, Inches(0.6), Inches(7.15), Inches(8), Inches(0.28), ["EPLKK — ekstrak klaim, simpan PKS, bandingkan"], size=11, color=MUTED)
    add_text(s, Inches(11.4), Inches(7.15), Inches(1.4), Inches(0.28), [f"14 / {total}"], size=11, color=MUTED, align=PP_ALIGN.RIGHT)

    OUT_ID.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT_ID)
    return OUT_ID


if __name__ == "__main__":
    print(build())
    print(build_id())
