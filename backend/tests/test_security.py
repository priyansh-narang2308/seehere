"""Security audit checks (Task 32): every write needs the app header, rate limits, security
headers, no secrets in the repository."""

from __future__ import annotations

import re
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from seehere.api.main import app
from seehere.api.security import SECURITY_HEADERS, Limit, RateLimiter, limit_for
from seehere.core.config import Settings, get_settings

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        media_dir=tmp_path / "media",
        rate_limit_reads_per_minute=5,
        rate_limit_writes_per_minute=3,
        rate_limit_uploads_per_hour=2,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _write_operations() -> list[tuple[str, str]]:
    ops = []
    for path, methods in app.openapi()["paths"].items():
        for method in methods:
            if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                ops.append((method.upper(), re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)))
    return ops


def test_every_write_needs_the_app_header(client: TestClient, settings: Settings) -> None:
    """A cross-site form or fetch cannot add this header without a CORS preflight, which only
    the app's own origin passes, so no other site can trigger a write."""
    unlimited = settings.model_copy(update={"rate_limit_enabled": False})
    app.dependency_overrides[get_settings] = lambda: unlimited
    ops = _write_operations()
    assert len(ops) >= 5  # upload, cancel, retry, deck, review
    for method, url in ops:
        r = client.request(method, url, content=b"{}")
        assert r.status_code == 403, (method, url, r.status_code)
        assert r.json()["error"]["code"] == "missing_request_header"


def test_cross_site_preflight_is_refused_and_own_origin_allowed(client: TestClient) -> None:
    ask = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-seehere-request",
    }
    bad = client.options("/api/projects", headers={"Origin": "https://evil.example", **ask})
    assert "access-control-allow-origin" not in bad.headers
    good = client.options("/api/projects", headers={"Origin": "http://localhost:3000", **ask})
    assert good.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_reads_writes_and_uploads_have_separate_limits(client: TestClient) -> None:
    for _ in range(5):
        assert client.get("/api/projects").status_code == 200
    r = client.get("/api/projects")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(r.headers["Retry-After"]) <= 60
    assert all(r.headers[k] == v for k, v in SECURITY_HEADERS.items())

    nobody = uuid.uuid4()
    codes = [client.post(f"/api/jobs/{nobody}/retry").status_code for _ in range(4)]
    assert codes == [403, 403, 403, 429]  # writes count even when refused
    uploads = [client.post("/api/projects").status_code for _ in range(3)]
    assert uploads == [403, 403, 429]
    assert client.get("/api/health/live").status_code == 200  # health is never limited


def test_limiter_window_slides_and_clients_are_separate() -> None:
    now = [0.0]
    limiter = RateLimiter(clock=lambda: now[0])
    limit = Limit("read", 2, 60.0)
    assert [limiter.check("a", limit) for _ in range(2)] == [0.0, 0.0]
    assert limiter.check("a", limit) == pytest.approx(60.0)
    assert limiter.check("b", limit) == 0.0
    now[0] = 59.0
    assert limiter.check("a", limit) == pytest.approx(1.0)
    now[0] = 60.5
    assert limiter.check("a", limit) == 0.0


def test_limits_classify_requests(settings: Settings) -> None:
    pid = uuid.uuid4()
    assert limit_for(settings, "POST", "/api/projects").bucket == "upload"  # type: ignore[union-attr]
    assert limit_for(settings, "POST", f"/api/projects/{pid}/deck").bucket == "upload"  # type: ignore[union-attr]
    assert limit_for(settings, "POST", f"/api/cues/{pid}/review").bucket == "write"  # type: ignore[union-attr]
    assert limit_for(settings, "GET", f"/api/projects/{pid}/video").bucket == "read"  # type: ignore[union-attr]
    assert limit_for(settings, "GET", "/api/health") is None
    off = settings.model_copy(update={"rate_limit_enabled": False})
    assert limit_for(off, "POST", "/api/projects") is None


def test_forwarded_address_is_used_only_behind_a_trusted_proxy(settings: Settings) -> None:
    from starlette.requests import Request

    from seehere.api.security import client_address

    scope = {
        "type": "http",
        "client": ("10.0.0.2", 1234),
        "headers": [(b"x-forwarded-for", b"203.0.113.7, 10.0.0.2")],
    }
    request = Request(scope)
    assert client_address(request, settings) == "10.0.0.2"
    trusted = settings.model_copy(update={"trust_proxy_headers": True})
    assert client_address(request, trusted) == "203.0.113.7"


def test_every_response_has_security_headers(client: TestClient) -> None:
    for url in ("/api/projects", f"/api/projects/{uuid.uuid4()}", "/api/health/live"):
        r = client.get(url)
        for name, value in SECURITY_HEADERS.items():
            assert r.headers.get(name) == value, (url, name)
    docs = client.get("/api/docs")
    assert "content-security-policy" not in docs.headers  # Swagger UI loads its own scripts
    assert docs.headers["x-frame-options"] == "DENY"


def test_no_secrets_are_tracked_in_git() -> None:
    files = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.split()
    assert not [f for f in files if Path(f).name == ".env" or f.endswith((".pem", ".key"))]
    pattern = re.compile(
        r"(VULTR_INFERENCE_API_KEY|VULTR_API_KEY)\s*=\s*[A-Za-z0-9]{16,}"
        r"|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    )
    leaks = []
    for f in files:
        path = REPO / f
        if path.suffix in {".png", ".jpg", ".ico", ".woff2", ".lock"} or not path.is_file():
            continue
        if pattern.search(path.read_text("utf-8", errors="ignore")):
            leaks.append(f)
    assert leaks == []
