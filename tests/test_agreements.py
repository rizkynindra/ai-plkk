import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import CostLine
from app.services.agreements.match import compare_lines
from app.services.agreements.parse import CatalogItem, parse_pks_document
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
