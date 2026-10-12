import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import CostLine
from app.services.agreements.match import compare_lines
from app.services.agreements.pages import AGREEMENTS_PAGE, CATALOG_PAGE
from app.services.agreements.parse import CatalogItem, parse_pks_document
from app.services.agreements.service import (
    draft_from_payload,
    get_branch_catalog,
    preview_pks,
    save_agreement,
)

TARIFF_HEADERS = [
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
]
from app.services.agreements.store import reset_connection

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
client = TestClient(app)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "agreements_db_path", tmp_path / "agreements.db")
    reset_connection()
    yield
    reset_connection()


def test_parse_tarif_pelni_pdf() -> None:
    data = (SAMPLES / "TARIF PELNI.pdf").read_bytes()
    draft = parse_pks_document(data, "TARIF PELNI.pdf")
    names = {item.item_name.upper(): item for item in draft.items}
    assert draft.group_name.lower().find("pelni") >= 0
    assert draft.city.lower() == "jakarta"
    assert "ADMINISTRASI RAWAT JALAN BARU" in names
    assert names["ADMINISTRASI RAWAT JALAN BARU"].tariff == 75_000
    assert any("DOKTER UMUM/DOKTER GIGI UMUM" == item.item_name.upper() and item.tariff == 200_000 for item in draft.items)
    assert len(draft.items) > 50


def test_compare_flags_price_mismatch() -> None:
    catalog = [
        CatalogItem(item_name="HOMECARE", tariff=50_000, item_code="HC1"),
        CatalogItem(item_name="ADMINISTRASI RAWAT JALAN BARU", tariff=75_000, item_code="BA0001"),
    ]
    lines = [
        CostLine(sequence_no=1, item_name="HOMECARE", quantity=2, tariff=50_000, discounted_cost=100_000),
        CostLine(sequence_no=2, item_name="Administrasi Rawat Jalan Baru", quantity=1, tariff=80_000, discounted_cost=80_000),
        CostLine(sequence_no=3, item_name="Unknown Drug", quantity=1, tariff=1000, discounted_cost=1000),
    ]
    compared = compare_lines(lines, catalog)
    assert compared[0]["match_status"] == "matched"
    assert compared[1]["match_status"] == "price_mismatch"
    assert compared[2]["match_status"] == "unmatched"


def test_agreement_preview_and_save_and_compare(temp_db) -> None:
    path = SAMPLES / "TARIF PELNI.pdf"
    preview = client.post("/api/agreements/preview", files={"file": (path.name, path.read_bytes(), "application/pdf")})
    assert preview.status_code == 200
    body = preview.json()
    assert body["item_count"] > 50
    body["branch_name"] = "RS Pelni Jakarta Selatan"
    saved = client.post("/api/agreements", json=body)
    assert saved.status_code == 200
    branch_id = saved.json()["branch_id"]
    hospitals = client.get("/api/hospitals")
    assert hospitals.status_code == 200
    assert any(row["branch_name"] == "RS Pelni Jakarta Selatan" for row in hospitals.json())

    compared = client.post(
        "/api/compare",
        json={
            "branch_id": branch_id,
            "lines": [
                {
                    "sequence_no": 1,
                    "item_name": "ADMINISTRASI RAWAT JALAN BARU",
                    "quantity": 1,
                    "tariff": 75000,
                    "discounted_cost": 75000,
                }
            ],
        },
    )
    assert compared.status_code == 200
    assert compared.json()["lines"][0]["match_status"] == "matched"
    catalog = client.get(f"/api/hospitals/{branch_id}")
    assert catalog.status_code == 200
    assert catalog.json()["item_count"] > 50


def test_agreement_base64_preview_and_save(temp_db) -> None:
    path = SAMPLES / "TARIF PELNI.pdf"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    preview = client.post(
        "/api/agreements/preview/base64",
        json={
            "chId": "CH-PKS",
            "reqId": "REQ-PKS",
            "docBase64": encoded,
            "filename": path.name,
        },
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["chId"] == "CH-PKS"
    assert body["item_count"] > 50

    saved = client.post(
        "/api/agreements/base64",
        json={
            "chId": "CH-PKS",
            "reqId": "REQ-PKS",
            "docBase64": encoded,
            "filename": path.name,
            "branch_name": "RS Pelni Jakarta Selatan",
        },
    )
    assert saved.status_code == 200
    result = saved.json()
    assert result["chId"] == "CH-PKS"
    assert result["reqId"] == "REQ-PKS"
    assert result["branch_name"] == "RS Pelni Jakarta Selatan"
    assert result["item_count"] > 50
    assert result["branch_id"] >= 1


def test_convert_rejects_tarif_book() -> None:
    path = SAMPLES / "TARIF PELNI.pdf"
    response = client.post("/api/convert", files={"file": (path.name, path.read_bytes(), "application/pdf")})
    assert response.status_code == 422


def test_text_pdf_without_item_codes_extracts_prices() -> None:
    data = _text_pdf(
        [
            "KONSULTASI DOKTER",
            "1 Konsultasi Dokter Umum 1.500.000",
            "2 Konsultasi Dokter Spesialis 2.250.000",
            "KAMAR PERAWATAN",
            "Kelas III Kelas II Kelas I",
            "Rawat Inap 500.000 750.000 1.000.000",
        ]
    )
    draft = parse_pks_document(data, "PKS RS COLUMBIA ASIA BSD.pdf")
    by_name = {item.item_name: item for item in draft.items}
    assert draft.method == "pdf-text"
    assert by_name["Konsultasi Dokter Umum"].tariff == 1_500_000
    assert by_name["Konsultasi Dokter Umum"].kelompok == "KONSULTASI DOKTER"
    assert by_name["Rawat Inap Kelas III"].tariff == 500_000
    assert by_name["Rawat Inap Kelas I"].tariff == 1_000_000
    assert by_name["Rawat Inap Kelas I"].kelompok == "KAMAR PERAWATAN"


def test_coded_text_pdf_keeps_item_code() -> None:
    data = _text_pdf(
        [
            "BIAYA ADMINISTRASI",
            "BA0001 ADMINISTRASI RAWAT JALAN BARU 75.000",
        ]
    )
    draft = parse_pks_document(data, "TARIF PELNI.pdf")
    assert draft.method == "pdf-text"
    assert draft.items[0].item_code == "BA0001"
    assert draft.items[0].tariff == 75_000


def test_scanned_pdf_uses_ocr_text(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.agreements.parse.ocr_pil_image",
        lambda image: "KONSULTASI DOKTER\n1 Konsultasi Dokter Umum 1.500.000\n",
    )
    draft = parse_pks_document(_scan_pdf(), "PKS RS COLUMBIA ASIA BSD.pdf")
    assert draft.method == "pdf-ocr"
    assert draft.items[0].item_name == "Konsultasi Dokter Umum"
    assert draft.items[0].tariff == 1_500_000


def test_unreadable_scan_uses_vision(monkeypatch) -> None:
    monkeypatch.setattr("app.services.agreements.parse.ocr_pil_image", lambda image: "")
    monkeypatch.setattr("app.services.agreements.parse.vision_service_reachable", lambda timeout_seconds=2.0: True)
    monkeypatch.setattr(
        "app.services.agreements.parse.extract_pks_tariffs_from_pdf",
        lambda data, page_indexes: [
            {
                "kelompok": "KONSULTASI DOKTER",
                "item_name": "Konsultasi Dokter Umum",
                "tariff": 1_500_000,
                "tariff_note": "",
                "source_page": 1,
            }
        ],
    )
    draft = parse_pks_document(_scan_pdf(), "PKS RS COLUMBIA ASIA BSD.pdf")
    assert draft.method == "pdf-vision"
    assert draft.items[0].tariff == 1_500_000
    assert draft.items[0].kelompok == "KONSULTASI DOKTER"


def test_agreement_preview_reports_elapsed() -> None:
    data = _text_pdf(
        [
            "KONSULTASI DOKTER",
            "1 Konsultasi Dokter Umum 1.500.000",
        ]
    )
    response = client.post("/api/agreements/preview", files={"file": ("pks.pdf", data, "application/pdf")})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["elapsed_seconds"], (int, float))
    assert body["elapsed_seconds"] >= 0
    assert 'id="preview-elapsed"' in AGREEMENTS_PAGE
    assert "Processing time" in AGREEMENTS_PAGE


def test_preview_rows_use_workbook_headers() -> None:
    body = preview_pks(
        _text_pdf(
            [
                "KONSULTASI DOKTER",
                "1 Konsultasi Dokter Umum 1.500.000",
                "KAMAR PERAWATAN",
                "Kelas III Kelas II Kelas I",
                "Rawat Inap 500.000 750.000 1.000.000",
            ]
        ),
        "PKS RS COLUMBIA ASIA BSD.pdf",
    )
    assert list(body["items"][0]) == TARIFF_HEADERS
    umum = next(row for row in body["items"] if row["nama"] == "Konsultasi Dokter Umum")
    assert umum["kategori_bpjs"] == "KONSULTASI DOKTER"
    assert umum["price"] == umum["price_base"] == umum["price_final"] == 1_500_000
    assert umum["hospital_name"] == body["branch_name"]
    kelas = next(row for row in body["items"] if row["group_code"] == "Kelas I")
    assert kelas["nama"] == "Rawat Inap Kelas I"
    assert kelas["price_final"] == 1_000_000
    assert kelas["source_page"] == 1
    for header in TARIFF_HEADERS:
        assert f">{header}<" in AGREEMENTS_PAGE
        assert f">{header}<" in CATALOG_PAGE


def test_saved_catalog_keeps_workbook_headers(temp_db) -> None:
    body = preview_pks(
        _text_pdf(
            [
                "BIAYA ADMINISTRASI",
                "BA0001 ADMINISTRASI RAWAT JALAN BARU 75.000",
            ]
        ),
        "TARIF PELNI.pdf",
    )
    saved = save_agreement(draft_from_payload(body))
    catalog = get_branch_catalog(saved["branch_id"])
    row = catalog["items"][0]
    assert list(row) == TARIFF_HEADERS
    assert row["kode_master"] == "BA0001"
    assert row["kategori_bpjs"] == "BIAYA ADMINISTRASI"
    assert row["price"] == row["price_base"] == row["price_final"] == 75_000
    assert row["hospital_name"] == body["branch_name"]
    assert row["source_page"] == 1


def test_unreadable_scan_explains_missing_reader(monkeypatch) -> None:
    monkeypatch.setattr("app.services.agreements.parse.ocr_pil_image", lambda image: "")
    monkeypatch.setattr("app.services.agreements.parse.vision_service_reachable", lambda timeout_seconds=2.0: False)
    with pytest.raises(ValueError, match="scan with no text layer"):
        parse_pks_document(_scan_pdf(), "PKS RS COLUMBIA ASIA BSD.pdf")


def _text_pdf(lines: list[str]) -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=12)
        y += 18
    data = document.tobytes()
    document.close()
    return data


def _scan_pdf() -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), 1)
    pixmap.clear_with(255)
    page.insert_image(page.rect, pixmap=pixmap)
    data = document.tobytes()
    document.close()
    return data
