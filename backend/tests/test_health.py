from fastapi.testclient import TestClient

from seehere.api.health import build_report, check_binary
from seehere.api.main import create_app
from seehere.core.config import Settings


def test_liveness() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_missing_binary_is_reported_down() -> None:
    result = check_binary("definitely-not-a-real-binary-xyz", ["--version"])
    assert result.status == "down"


def test_unreachable_database_makes_report_down_without_leaking_url() -> None:
    settings = Settings(database_url="postgresql+psycopg://u:secret@127.0.0.1:1/x")
    report = build_report(settings, "test")
    assert report.components["database"].status == "down"
    assert report.status == "down"
    assert "secret" not in report.model_dump_json()


def test_no_provider_keys_is_degraded_not_ok() -> None:
    settings = Settings(vultr_inference_api_key=None, gemini_api_key=None, smallest_api_key=None)
    report = build_report(settings, "test")
    assert report.components["ai_providers"].status == "degraded"


def test_readiness_endpoint_shape() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert set(body["components"]) == {"database", "ffmpeg", "ffprobe", "tesseract", "ai_providers"}
