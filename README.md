# EPLKK Claim to Template_Biaya

Local service for Indonesian hospital claims.

1. **Extract** a claim invoice (PDF, Excel, Word, CSV, or image) into **Template_Biaya**: `No`, `Item Biaya`, `Jumlah`, `Tarif`, `Biaya`. Billed text is copied as-is.
2. **Store** each hospital **branch** cooperation agreement (PKS / tarif book).
3. **Compare** billed rows to that branch catalog. Names and amounts stay as billed; the UI only flags `matched`, `price_mismatch`, or `unmatched`.

Convert does **not** rewrite items onto the IKS list. Posting a tarif book or `Daftar_Biaya_IKS` to `/api/convert` returns **422**. Use **Upload PKS** instead.

Scanned *gabungan* invoices use **Qwen3-VL** via Ollama. PKS PDFs such as `TARIF PELNI.pdf` are parsed from the text layer first; vision/OCR runs only on image-only pages.

## What you need

| Requirement | Notes |
| --- | --- |
| Python 3.12+ | Developed with 3.12. A virtualenv is expected. |
| NVIDIA GPU | Recommended for claim vision. Qwen3-VL 8B-instruct fits one 24 GB card at `VISION_CONTEXT_SIZE=32768`. |
| [Ollama](https://ollama.com) | Serves `qwen3-vl:8b-instruct`. |
| Tesseract (optional) | Image OCR fallback. Scanned claims use vision. |
| `rapidfuzz` | Installed via `requirements.txt`. Used for PKS name matching (no vector database). |

Supported uploads: `.pdf`, `.xlsx`, `.xls`, `.csv`, `.docx`, `.jpg` / `.jpeg`, `.png`, `.webp`, `.tif` / `.tiff`, `.bmp`.

## 1. Clone and Python env

```bash
cd /path/to/AI-EPLKK
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Install Ollama and the vision model

```bash
ollama pull qwen3-vl:8b-instruct
ollama serve
```

Leave Ollama on `http://127.0.0.1:11434`. Confirm `qwen3-vl:8b-instruct` in `curl -s http://127.0.0.1:11434/api/tags`. Do **not** use `qwen3-vl:8b` (thinking).

Custom model dir:

```bash
OLLAMA_MODELS=/media/rizkynindra/Data1/OLLAMA_MODELS ollama serve
```

## 3. Configuration

```bash
cp .env.example .env
```

Load `.env` from the **repo root** (Pydantic Settings in `app/config.py`). Environment variables override the file.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VISION_ENABLED` | `true` | Qwen3-VL for empty tables / scans. |
| `VISION_MODEL` | `qwen3-vl:8b-instruct` | Must match an Ollama tag. |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434/v1` | `/v1` is stripped for `/api/chat`. |
| `TEMPLATE_PATH` | `samples/Template_Biaya_KL26052203866176.xlsx` | Excel shell. |
| `VISION_CONTEXT_SIZE` | `32768` | Extract context. |
| `VISION_CLASSIFY_CONTEXT_SIZE` | `8192` | Billing-page classify. |
| `VISION_PARALLEL_REQUESTS` | `2` | Concurrent crop calls. |
| `VISION_MIN_DETAIL_LINES` | `20` | Stop scanning a gabungan after a dense billing block. |
| `AGREEMENTS_DB_PATH` | `data/agreements.db` | SQLite for hospitals, branches, PKS rows (gitignored). |
| `LLM_PROVIDER` | `none` | Text LLM unused for convert. |

## 4. Run the service

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

systemd (no `--reload`):

```bash
sudo cp deploy/ai-eplkk.service /etc/systemd/system/ai-eplkk.service
sudo systemctl daemon-reload
sudo systemctl enable --now ai-eplkk
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). The top menu is:

| Menu | URL | Job |
| --- | --- | --- |
| Claim invoice | `/` | Extract billed lines → Template_Biaya |
| Upload PKS | `/agreements` | Read tarif book, edit hospital/branch, save |
| PKS data | `/catalog` | Browse stored tariff rows |
| Compare | `/compare` | Extract a claim and flag vs a branch catalog |

On a phone, use **Menu** to open those links.

## 5. Tutorial: how to use it

Do **Upload PKS** once per hospital branch, then extract and compare claims. Catalogs persist in SQLite. Claim previews live **in memory**: do not restart uvicorn between extract and “Compare with PKS” on the preview page.

### 5.1 Save a PKS (example: RS Pelni)

1. Open **Upload PKS**.
2. Drop `samples/TARIF PELNI.pdf` (118-page tarif book). Text tables are parsed without running vision on every page.
3. The form fills **Rumah Sakit PELNI**, **Jakarta**, and an effective date from the letter. Rename the **branch** if you need a site (for example Jakarta Selatan vs Malang).
4. Click **Save branch catalog**. You should see a count of tariff rows (`CODE` + name + tarif).
5. Open **PKS data**, pick the branch, and scroll the table (e.g. `BA0001 ADMINISTRASI RAWAT JALAN BARU` = 75.000).

A second branch (Malang) is a new save with a different branch name, not an overwrite of Jakarta unless you keep the same branch name.

### 5.2 Extract a claim invoice

1. Open **Claim invoice**.
2. Drop a file (or click the zone).
3. Click **Extract billed lines**. A timer runs until the table appears.
4. Check rows, then **Download Template_Biaya.xlsx**.

Smoke test (no GPU): `samples/Template_Biaya_sample.xlsx` → `BIAYA ADMINISTRASI` and `HOMECARE`.

Vision test: `samples/KL26050404910135_gabung.pdf` → **74** itemized rows totaling **Rp 23.559.342** (a few minutes on one 24 GB GPU).

On that preview you can also pick a PKS branch and **Compare with PKS** without leaving the page.

### 5.3 Compare claim vs PKS (UI)

**One shot**

1. PKS already saved (5.1).
2. Open **Compare**.
3. Select the branch.
4. Drop the claim, click **Extract and compare**.
5. Read **Matched**, **Price differs**, **Unmatched**, then the row table (invoice tarif vs PKS item/tarif). Invoice names are not rewritten.

**After extract**

On the claim preview, select the same branch → **Compare with PKS**.

**What you should expect**

| Input | Typical result |
| --- | --- |
| Line `ADMINISTRASI RAWAT JALAN BARU` tarif 75.000 vs TARIF PELNI | `matched` |
| Same name, tarif 80.000 | `price_mismatch` |
| `HOMECARE` from the tiny sample vs TARIF PELNI | `unmatched` (not in that book) |
| Gabungan 74 drug/tindakan names vs Pelni `CODE` labels | many `unmatched` (different wording, not a failed extract) |

### 5.4 Quick API checks

Convert (see section 7 for Postman):

```bash
curl -sS -F "file=@samples/Template_Biaya_sample.xlsx" http://127.0.0.1:8000/api/convert | python3 -m json.tool
```

PKS + compare (see section 8).

## 6. HTTP API

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/` | Claim upload UI |
| `GET` | `/agreements` | PKS upload + edit hospital fields |
| `GET` | `/catalog` | Browse saved PKS rows |
| `GET` | `/compare` | Extract + compare UI |
| `POST` | `/preview` | Multipart claim → HTML preview (in-memory id) |
| `GET` | `/preview/{id}` | Re-open preview |
| `GET` | `/preview/{id}/xlsx` | Download Template_Biaya.xlsx |
| `POST` | `/api/convert` | Multipart claim → JSON |
| `POST` | `/api/convert/base64` | JSON `{chId, reqId, docBase64}` |
| `POST` | `/api/convert/xlsx` | Multipart claim → xlsx |
| `GET` | `/api/hospitals` | Groups and branches |
| `GET` | `/api/hospitals/{branch_id}` | Branch + latest tariff rows |
| `POST` | `/api/agreements/preview` | Multipart PKS → draft (no DB write) |
| `POST` | `/api/agreements/preview/base64` | JSON `{chId, reqId, docBase64}` → draft |
| `POST` | `/api/agreements` | JSON draft → SQLite |
| `POST` | `/api/agreements/base64` | JSON `{chId, reqId, docBase64}` parse + save |
| `POST` | `/api/compare` | `{branch_id, lines}` or `{branch_id, conversion_id}` |

Errors: `400` empty/invalid base64, `415` bad type, `422` not a claim (IKS xlsx, `TARIF PELNI.pdf` on convert, or no billed lines), `404` unknown branch or expired preview.

## 7. Test the convert API (Postman)

Replace `<server>` with the host (L4 box or `127.0.0.1`). Base64 convert has no filename; type is guessed from bytes. `chId` and `reqId` are echoed.

### 7.1 Encode the file

macOS: `base64 -i samples/Template_Biaya_sample.xlsx | pbcopy`  
Linux: `base64 -w0 samples/Template_Biaya_sample.xlsx`

A `data:application/pdf;base64,...` prefix is accepted.

### 7.2 Postman — JSON base64

**POST** `http://<server>:8000/api/convert/base64`  
Header `Content-Type: application/json`

```json
{
  "chId": "CH-001",
  "reqId": "REQ-001",
  "docBase64": "paste the copied base64 here"
}
```

Tiny sample success: `written_count` 2, `BIAYA ADMINISTRASI` and `HOMECARE`. `chId` / `reqId` required. `docBase64` is the file, not a path.

```bash
DOC=$(base64 -w0 samples/Template_Biaya_sample.xlsx)
curl -sS http://127.0.0.1:8000/api/convert/base64 \
  -H 'Content-Type: application/json' \
  -d "{\"chId\":\"CH-001\",\"reqId\":\"REQ-001\",\"docBase64\":\"$DOC\"}"
```

### 7.3 Postman — multipart

**POST** `/api/convert` → Body form-data key `file`. Download xlsx: `/api/convert/xlsx` or `?download=true`.

| Request | Expected |
| --- | --- |
| `Template_Biaya_sample.xlsx` `/api/convert/base64` | `200`, 2 lines |
| `Daftar_Biaya_IKS_*.xlsx` or `TARIF PELNI.pdf` on convert | `422` |
| Invalid base64 | `400` |
| `KL26050404910135_gabung.pdf` | `200`, 74 rows (GPU + Ollama) |

## 8. Test the PKS and compare APIs

Do **not** post a tarif book to `/api/convert`. For a JSON client like convert, use **`POST /api/agreements/base64`**. Multipart preview + `POST /api/agreements` is the two-step path if you need to edit the draft first.

### 8.1 Preview a PKS (no DB write)

**POST** `http://<server>:8000/api/agreements/preview`  
Body: form-data, key `file` (PDF, xlsx, or the same types as convert).

```bash
curl -sS -F "file=@samples/TARIF PELNI.pdf" \
  http://127.0.0.1:8000/api/agreements/preview \
  | python3 -m json.tool > /tmp/pks-draft.json
```

Response fields (edit before save): `group_name`, `branch_name`, `city`, `address`, `code`, `aliases`, `effective_date`, `source_filename`, `method`, `item_count`, `items[]` (`item_code`, `item_name`, `kelompok`, `tariff`, `tariff_note`, `source_page`).

Empty file → `400`. Unsupported type → `415`. No tariff rows → `422`.

### 8.2 Save the draft to SQLite

**POST** `http://<server>:8000/api/agreements`  
Header `Content-Type: application/json`. Send the preview JSON (optionally change `branch_name` first). Extra keys such as `item_count` are ignored.

```bash
jq '.branch_name = "RS Pelni Jakarta Selatan"' /tmp/pks-draft.json > /tmp/pks-save.json

curl -sS http://127.0.0.1:8000/api/agreements \
  -H 'Content-Type: application/json' \
  -d @/tmp/pks-save.json \
  | python3 -m json.tool
```

Success:

```json
{
  "agreement_id": 1,
  "branch_id": 1,
  "item_count": 123,
  "group_name": "Rumah Sakit PELNI",
  "branch_name": "RS Pelni Jakarta Selatan"
}
```

The same `group_name` + `branch_name` updates that branch and inserts a **new** agreement (latest catalog is used for compare). A different `branch_name` (for example Malang) creates another branch.

Postman: Collection → POST `/api/agreements/preview` (form-data `file`) → copy the JSON body into POST `/api/agreements`.

### 8.3 One-shot JSON base64 (same shape as convert)

**POST** `http://<server>:8000/api/agreements/base64`  
Header `Content-Type: application/json`

`docBase64` is the PKS file (PDF/xlsx), not a path. Type is guessed from bytes unless you send `filename` (recommended for `TARIF PELNI.pdf`). Optional hospital fields override what the parser inferred. `chId` and `reqId` are echoed.

```json
{
  "chId": "CH-001",
  "reqId": "REQ-001",
  "docBase64": "paste the copied base64 here",
  "filename": "TARIF PELNI.pdf",
  "branch_name": "RS Pelni Jakarta Selatan"
}
```

Optional overrides: `group_name`, `branch_name`, `city`, `address`, `code`, `aliases`, `effective_date`.

```bash
DOC=$(base64 -w0 samples/TARIF PELNI.pdf)
curl -sS http://127.0.0.1:8000/api/agreements/base64 \
  -H 'Content-Type: application/json' \
  -d "{\"chId\":\"CH-001\",\"reqId\":\"REQ-001\",\"filename\":\"TARIF PELNI.pdf\",\"branch_name\":\"RS Pelni Jakarta Selatan\",\"docBase64\":\"$DOC\"}"
```

Success (same as 8.2, plus `chId` / `reqId`):

```json
{
  "agreement_id": 1,
  "branch_id": 1,
  "item_count": 123,
  "group_name": "Rumah Sakit PELNI",
  "branch_name": "RS Pelni Jakarta Selatan",
  "chId": "CH-001",
  "reqId": "REQ-001"
}
```

Parse only (no SQLite write): **POST** `/api/agreements/preview/base64` with the same JSON. Then POST the returned draft to `/api/agreements` if you need to edit items first.

A `data:application/pdf;base64,...` prefix is accepted. Invalid base64 → `400`. No tariff rows → `422`.

### 8.4 List hospitals and read a catalog

```bash
curl -sS http://127.0.0.1:8000/api/hospitals | python3 -m json.tool
```

Each row: `branch_id`, `group_name`, `branch_name`, `city`, `address`, `code`, `aliases`, `item_count`.

```bash
curl -sS http://127.0.0.1:8000/api/hospitals/1 | python3 -m json.tool
```

Adds `items[]` (latest PKS for that branch). Unknown `branch_id` → `404`.

### 8.5 Compare billed lines to a branch

**POST** `http://<server>:8000/api/compare`  
Header `Content-Type: application/json`.

Send **either** `lines` **or** `conversion_id` (in-memory id from `POST /preview`, not from `/api/convert`). Restarting uvicorn drops `conversion_id`.

**With explicit lines** (typical API client):

```bash
curl -sS http://127.0.0.1:8000/api/compare \
  -H 'Content-Type: application/json' \
  -d '{
    "branch_id": 1,
    "lines": [
      {
        "sequence_no": 1,
        "item_name": "ADMINISTRASI RAWAT JALAN BARU",
        "quantity": 1,
        "tariff": 75000,
        "discounted_cost": 75000
      }
    ]
  }' | python3 -m json.tool
```

**After a claim extract**, reuse convert JSON:

```bash
curl -sS -F "file=@samples/Template_Biaya_sample.xlsx" \
  http://127.0.0.1:8000/api/convert > /tmp/claim.json

jq '{branch_id: 1, lines: .lines}' /tmp/claim.json \
  | curl -sS http://127.0.0.1:8000/api/compare \
      -H 'Content-Type: application/json' \
      -d @- | python3 -m json.tool
```

**With preview id** (same process as the UI “Compare with PKS”):

```bash
curl -sS http://127.0.0.1:8000/api/compare \
  -H 'Content-Type: application/json' \
  -d '{"branch_id":1,"conversion_id":"<id from /preview HTML data-conversion-id>"}'
```

Success includes `branch_id`, `catalog_size`, `counts` (`matched`, `price_mismatch`, `unmatched`, `ambiguous`), and `lines[]` with `match_status`, PKS `item_code` / name / tarif when a name hits. Invoice `item_name` and `tariff` are not rewritten.

| Request | Expected |
| --- | --- |
| Preview `TARIF PELNI.pdf` | `200`, `item_count` > 50, Pelni / Jakarta |
| `/api/agreements/base64` with that PDF | `200`, `branch_id`, echoed `chId` / `reqId` |
| Save draft with a new `branch_name` | `200`, `branch_id` |
| Compare `ADMINISTRASI RAWAT JALAN BARU` 75000 | `matched` |
| Same name, tarif 80000 | `price_mismatch` |
| `HOMECARE` vs TARIF PELNI | `unmatched` |
| Missing `lines` and `conversion_id` | `400` |
| Unknown / empty catalog `branch_id` | `404` |
| Expired `conversion_id` | `404` |

## 9. Tests

```bash
source .venv/bin/activate
python -m pytest -q
```

Covers extract heuristics, IKS/tarif-book rejection, TARIF PELNI parse, match flags, and HTML routes. They do **not** call Ollama.

## Project layout

```
app/main.py                      Routes (convert + PKS + compare)
app/web.py                       Shared nav / page chrome
app/config.py                    Settings (.env)
app/static/                      CSS, upload / PKS / catalog / compare JS
app/services/convert.py          Claim extract
app/services/vision.py           Qwen3-VL for scanned claims
app/services/agreements/         SQLite store, PKS parse, rapidfuzz match
app/services/template.py         Fill Template_Biaya
app/services/preview.py          Claim preview HTML
DESIGN.md                        UI direction
data/agreements.db               Created at runtime (gitignored)
samples/
tests/
```

Claim scan pipeline: tables first → classify pages → 3-crop extract → walk neighbours → skip kuitansi/`INSTALASI` rollups → keep Biaya Administrasi.

PKS pipeline: PDF/xlsx text (`CODE` + tarif) → preview/edit hospital fields → SQLite per branch → compare by normalized name + tarif.

## Samples

| File | Use |
| --- | --- |
| `samples/Template_Biaya_KL26052203866176.xlsx` | Empty Template_Biaya shell |
| `samples/Template_Biaya_sample.xlsx` / `.pdf` | Tiny digital claim |
| `samples/KL26050404910135_gabung.pdf` | Scanned bundle (vision, 74 rows) |
| `samples/TARIF PELNI.pdf` | PKS tarif book for Upload PKS |
| `samples/Daftar_Biaya_IKS_*.xlsx` | Catalog; convert returns 422 (OK on Upload PKS) |

## Troubleshooting

**Empty claim preview on a scan.** `ollama ps` should show `qwen3-vl:8b-instruct` at 100% GPU. Not the thinking tag.

**Compare 404.** No catalog for that `branch_id`, or `conversion_id` expired after restart. Save PKS again or re-extract.

**Mostly unmatched vs TARIF PELNI.** Invoice wording (obat/tindakan) often differs from `CODE` labels. Try `ADMINISTRASI RAWAT JALAN BARU` at 75.000 to prove the matcher.

**CUDA OOM.** Lower `VISION_CONTEXT_SIZE` or `VISION_RENDER_SCALE`. Restart Ollama.

**`.env` not applied.** Run uvicorn from the repo root. `--reload` may not re-read `.env` until a full process restart.

## License / data

Claim PDFs in `samples/` may contain personal billing data. Do not publish them. `.env` and `data/*.db` are gitignored.
