import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
client = TestClient(app)


def test_convert_json_preview() -> None:
    path = SAMPLES / "Template_Biaya_sample.xlsx"
    response = client.post(
        "/api/convert",
        files={"file": (path.name, path.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["written_count"] == 2
    assert body["lines"][0]["item_name"] == "BIAYA ADMINISTRASI"
    assert isinstance(body["elapsed_seconds"], (int, float))
    assert body["elapsed_seconds"] >= 0


def test_convert_rejects_iks_catalog() -> None:
    path = SAMPLES / "Daftar_Biaya_IKS_20260917_022547.xlsx"
    response = client.post("/api/convert", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 422


def test_convert_base64_json_preview() -> None:
    path = SAMPLES / "Template_Biaya_sample.xlsx"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    response = client.post(
        "/api/convert/base64",
        json={"chId": "CH-1", "reqId": "REQ-1", "docBase64": encoded},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["chId"] == "CH-1"
    assert body["reqId"] == "REQ-1"
    assert body["written_count"] == 2
    assert body["lines"][0]["item_name"] == "BIAYA ADMINISTRASI"


def test_convert_base64_rejects_invalid_payload() -> None:
    response = client.post(
        "/api/convert/base64",
        json={"chId": "CH-1", "reqId": "REQ-1", "docBase64": "not-valid-base64!!!"},
    )
    assert response.status_code == 400


def test_convert_xlsx_download() -> None:
    path = SAMPLES / "Template_Biaya_sample.xlsx"
    response = client.post("/api/convert/xlsx", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]


def test_html_preview_lists_extracted_items() -> None:
    path = SAMPLES / "Template_Biaya_sample.xlsx"
    response = client.post("/preview", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "BIAYA ADMINISTRASI" in response.text
    assert "HOMECARE" in response.text
    assert "Compare with PKS" in response.text
    assert "Processing time" in response.text
    assert "Total biaya" not in response.text
    home = client.get("/")
    assert home.status_code == 200
    assert "dropzone" in home.text
    assert 'href="/agreements"' in home.text
    assert 'href="/catalog"' in home.text
    assert 'href="/compare"' in home.text
    compare_page = client.get("/compare")
    assert compare_page.status_code == 200
    assert "Extract and compare" in compare_page.text
    assert "/api/compare" in client.get("/static/compare.js").text
    agreements = client.get("/agreements")
    assert agreements.status_code == 200
    catalog = client.get("/catalog")
    assert catalog.status_code == 200
    assert "Select a saved branch" in catalog.text
    assert "/api/agreements/preview" in client.get("/static/agreements.js").text
    assert "/static/upload.js" in home.text
    styles = client.get("/static/styles.css")
    assert styles.status_code == 200
    script = client.get("/static/upload.js")
    assert script.status_code == 200
    assert "dataTransfer" in script.text
