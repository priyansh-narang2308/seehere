"""End-to-end tests of the upload endpoint with real videos made by ffmpeg, real ffprobe and
real Postgres (each test's rows are rolled back; files go to a per-test temp directory)."""

from __future__ import annotations

import hashlib
import subprocess
import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.db.models import MediaAsset, Project
from seehere.db.session import get_db

MAX_MB = 1
MAX_SECONDS = 3


def _ffmpeg(out: Path, *args: str) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, str(out)], check=True, timeout=60)
    return out


@pytest.fixture(scope="session")
def videos(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("videos")
    src = ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=10", "-f", "lavfi", "-i", "sine"]
    h264 = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"]
    files = {
        "mp4": _ffmpeg(d / "ok.mp4", *src, "-t", "2", *h264),
        "mov": _ffmpeg(d / "ok.mov", *src, "-t", "2", *h264, "-f", "mov"),
        "webm": _ffmpeg(
            d / "ok.webm", *src, "-t", "2", "-c:v", "libvpx-vp9", "-c:a", "libopus", "-shortest"
        ),
        "long": _ffmpeg(d / "long.mp4", *src, "-t", "5", *h264),
        "no_audio": _ffmpeg(
            d / "silent.mp4",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=10",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
        ),
        "png": _ffmpeg(
            d / "image.png", "-f", "lavfi", "-i", "testsrc=size=64x64", "-frames:v", "1"
        ),
    }
    playlist = d / "playlist.mp4"
    playlist.write_text("#EXTM3U\n#EXTINF:1,\nhttp://127.0.0.1:9/x.ts\n#EXT-X-ENDLIST\n")
    concat = d / "concat.mp4"
    concat.write_text("ffconcat version 1.0\nfile /etc/hosts\n")
    text = d / "notes.mp4"
    text.write_text("just some text pretending to be a video\n" * 20)
    files |= {"playlist": playlist, "concat": concat, "text": text}
    return files


@pytest.fixture
def media_dir(tmp_path: Path) -> Path:
    return tmp_path / "media"


@pytest.fixture
def client(db: Session, media_dir: Path) -> Iterator[TestClient]:
    settings = Settings(media_dir=media_dir, max_upload_mb=MAX_MB, max_video_duration_s=MAX_SECONDS)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _headers(
    title: str = "Lecture 7", filename: str = "lecture.mp4", rights: str | None = "true"
) -> dict[str, str]:
    h = {"X-SeeHere-Title": quote(title), "X-SeeHere-Filename": quote(filename)}
    if rights is not None:
        h["X-SeeHere-Rights-Confirmed"] = rights
    return h


def _upload(client: TestClient, path: Path, **kw: str | None) -> tuple[int, dict]:
    r = client.post("/api/projects", content=path.read_bytes(), headers=_headers(**kw))  # type: ignore[arg-type]
    return r.status_code, r.json()


def _stored_files(media_dir: Path) -> list[Path]:
    return [p for p in media_dir.rglob("*") if p.is_file()] if media_dir.exists() else []


def _count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Project)) or 0


# --- accepted uploads -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "ext", "mime", "vcodec"),
    [
        ("mp4", ".mp4", "video/mp4", "h264"),
        ("mov", ".mov", "video/quicktime", "h264"),
        ("webm", ".webm", "video/webm", "vp9"),
    ],
)
def test_accepts_supported_videos(
    client: TestClient,
    db: Session,
    media_dir: Path,
    videos: dict[str, Path],
    kind: str,
    ext: str,
    mime: str,
    vcodec: str,
) -> None:
    status, body = _upload(client, videos[kind], title="  Lecture 7 — Graphs  ")
    assert status == 201, body
    assert body["title"] == "Lecture 7 — Graphs"
    assert body["status"] == "uploaded"
    src = body["source"]
    assert (src["mime_type"], src["video_codec"], src["width"], src["height"]) == (
        mime,
        vcodec,
        320,
        240,
    )
    assert 1.9 <= src["duration_s"] <= 2.1
    # internal details stay internal
    assert "storage_path" not in src and "sha256" not in src

    media = db.scalar(select(MediaAsset).where(MediaAsset.project_id == body["id"]))
    assert media is not None
    assert media.storage_path == f"projects/{body['id']}/source{ext}"
    stored = media_dir / media.storage_path
    assert stored.read_bytes() == videos[kind].read_bytes()
    assert media.sha256 == hashlib.sha256(stored.read_bytes()).hexdigest()
    assert stored.stat().st_mode & 0o777 == 0o600
    assert "filename" not in media.probe["format"]  # temp path not persisted
    assert list((media_dir / "tmp").iterdir()) == []


def test_filename_is_sanitized_and_never_used_for_the_path(
    client: TestClient, db: Session, media_dir: Path, videos: dict[str, Path]
) -> None:
    status, body = _upload(client, videos["mp4"], filename="../../../etc/passwd\x07.mp4")
    assert status == 201
    assert body["source"]["original_filename"] == "passwd.mp4"
    assert _stored_files(media_dir) == [media_dir / f"projects/{body['id']}/source.mp4"]


# --- rejected before reading the body ---------------------------------------------------------


@pytest.mark.parametrize("rights", [None, "false", "TRUE", "1"])
def test_requires_rights_confirmation(
    client: TestClient, db: Session, media_dir: Path, videos: dict[str, Path], rights: str | None
) -> None:
    status, body = _upload(client, videos["mp4"], rights=rights)
    assert (status, body["error"]["code"]) == (400, "rights_not_confirmed")
    assert _count(db) == 0 and _stored_files(media_dir) == []


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
def test_requires_a_valid_title(
    client: TestClient, db: Session, videos: dict[str, Path], title: str
) -> None:
    status, body = _upload(client, videos["mp4"], title=title)
    assert (status, body["error"]["code"]) == (400, "invalid_title")
    assert _count(db) == 0


def test_rejects_declared_oversize_body(client: TestClient, db: Session, media_dir: Path) -> None:
    r = client.post("/api/projects", content=b"\0" * (MAX_MB * 1024 * 1024 + 1), headers=_headers())
    assert (r.status_code, r.json()["error"]["code"]) == (413, "too_large")
    assert _count(db) == 0 and _stored_files(media_dir) == []


def test_enforces_cap_while_streaming_without_content_length(
    client: TestClient, db: Session, media_dir: Path
) -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(3):
            yield b"\0" * (512 * 1024)  # 1.5 MiB in total, no Content-Length

    r = client.post("/api/projects", content=chunks(), headers=_headers())
    assert (r.status_code, r.json()["error"]["code"]) == (413, "too_large")
    assert _count(db) == 0 and _stored_files(media_dir) == []


def test_rejects_empty_body(client: TestClient, db: Session, media_dir: Path) -> None:
    r = client.post("/api/projects", content=b"", headers=_headers())
    assert (r.status_code, r.json()["error"]["code"]) == (400, "empty_file")
    assert _stored_files(media_dir) == []


# --- rejected by content ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "status", "code"),
    [
        # HLS playlist that would fetch a URL
        ("playlist", 415, "unsupported_format"),
        # concat list pointing at /etc/hosts
        ("concat", 415, "unsupported_format"),
        ("text", 415, "unsupported_format"),
        ("png", 415, "unsupported_format"),
        ("no_audio", 422, "no_audio_stream"),
        ("long", 422, "too_long"),
    ],
)
def test_rejects_by_content(
    client: TestClient,
    db: Session,
    media_dir: Path,
    videos: dict[str, Path],
    kind: str,
    status: int,
    code: str,
) -> None:
    got_status, body = _upload(client, videos[kind], filename="looks-fine.mp4")
    assert (got_status, body["error"]["code"]) == (status, code)
    assert body["error"]["message"]
    assert _count(db) == 0 and _stored_files(media_dir) == []


def test_database_failure_leaves_no_file(
    client: TestClient,
    db: Session,
    media_dir: Path,
    videos: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom() -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(db, "commit", boom)
    r = client.post("/api/projects", content=videos["mp4"].read_bytes(), headers=_headers())
    assert r.status_code == 500
    assert _stored_files(media_dir) == []


# --- reading projects -------------------------------------------------------------------------


def test_list_and_get_projects(client: TestClient, db: Session, videos: dict[str, Path]) -> None:
    _, first = _upload(client, videos["mp4"], title="First")
    _, second = _upload(client, videos["webm"], title="Second")
    # Both uploads share this test's transaction, where now() is constant; in real use each
    # upload is its own transaction. Make the order explicit.
    db.execute(
        update(Project)
        .where(Project.id == uuid.UUID(first["id"]))
        .values(created_at=Project.created_at - timedelta(minutes=1))
    )
    listed = client.get("/api/projects").json()
    assert [p["title"] for p in listed][:2] == ["Second", "First"]

    r = client.get(f"/api/projects/{first['id']}")
    assert r.status_code == 200 and r.json()["source"]["mime_type"] == "video/mp4"

    missing = client.get("/api/projects/3f2a9c1e-7b4d-4e8a-9c0f-1a2b3c4d5e6f")
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "not_found")
    bad = client.get("/api/projects/not-a-uuid")
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "invalid_request")


def test_upload_config_reports_real_limits(client: TestClient) -> None:
    body = client.get("/api/config/upload").json()
    assert body["max_upload_bytes"] == MAX_MB * 1024 * 1024
    assert body["max_video_duration_s"] == MAX_SECONDS
    assert ".mp4" in body["accept"]
    assert body["retention_hours"] == 24
