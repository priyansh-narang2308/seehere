"""The jobs and prepared-media API, end to end: upload over HTTP, run the real worker, then read
the outputs and frame images back over HTTP."""

from __future__ import annotations

import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.db.models import Frame
from seehere.db.session import get_db
from seehere.jobs.worker import Worker
from seehere.pipeline import HANDLERS

Sessions = sessionmaker[Session]
ACTION = {"X-SeeHere-Request": "1"}


@pytest.fixture(scope="module")
def video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("v") / "talk.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine",
            "-t",
            "5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(out),
        ],
        check=True,
        timeout=60,
    )
    return out


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.2)


@pytest.fixture
def client(sessions: Sessions, settings: Settings) -> Iterator[TestClient]:
    def db() -> Iterator[Session]:
        with sessions() as s:
            yield s

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _upload(client: TestClient, video: Path) -> dict:
    r = client.post(
        "/api/projects",
        content=video.read_bytes(),
        headers={
            "X-SeeHere-Title": quote("Lecture"),
            "X-SeeHere-Filename": "talk.mp4",
            "X-SeeHere-Rights-Confirmed": "true",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _jobs(client: TestClient, project_id: str) -> list[dict]:
    r = client.get(f"/api/projects/{project_id}/jobs")
    assert r.status_code == 200
    return r.json()["jobs"]


def test_upload_queues_media_preparation(client: TestClient, video: Path) -> None:
    project = _upload(client, video)
    assert project["status"] == "processing"
    [job] = _jobs(client, project["id"])
    assert (job["kind"], job["label"], job["status"], job["attempts"]) == (
        "media.prepare",
        "Media preparation",
        "queued",
        0,
    )
    body = client.get(f"/api/projects/{project['id']}/jobs").json()
    assert body["now"] >= job["created_at"]


def test_worker_outputs_are_served(
    client: TestClient, sessions: Sessions, settings: Settings, video: Path
) -> None:
    project = _upload(client, video)
    assert Worker(HANDLERS, settings=settings, sessions=sessions).run_once()

    job, speech = _jobs(client, project["id"])
    assert (job["status"], job["progress"], job["error"]) == ("succeeded", 1.0, None)
    # Preparation queues speech-to-text, so the project is still processing.
    assert (speech["kind"], speech["label"], speech["status"]) == (
        "speech.transcribe",
        "Speech-to-text",
        "queued",
    )
    assert client.get(f"/api/projects/{project['id']}").json()["status"] == "processing"

    media = client.get(f"/api/projects/{project['id']}/media?preview=3").json()
    assert media["audio"]["sample_rate"] == 16000 and media["audio"]["channels"] == 1
    assert media["audio"]["duration_s"] == pytest.approx(5, abs=0.05)
    frames = media["frames"]
    assert (frames["count"], frames["fps"], frames["first_s"], frames["last_s"]) == (5, 1.0, 0, 4)
    assert [f["t_s"] for f in frames["preview"]] == [0, 2, 4]

    r = client.get(f"/api/frames/{frames['preview'][0]['id']}/image")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.content[:2] == b"\xff\xd8"


def test_media_before_preparation_is_empty(client: TestClient, video: Path) -> None:
    project = _upload(client, video)
    media = client.get(f"/api/projects/{project['id']}/media").json()
    assert media == {
        "audio": None,
        "frames": {"count": 0, "fps": None, "first_s": None, "last_s": None, "preview": []},
    }


def test_cancel_and_retry(client: TestClient, video: Path) -> None:
    project = _upload(client, video)
    [job] = _jobs(client, project["id"])

    r = client.post(f"/api/jobs/{job['id']}/cancel")
    assert (r.status_code, r.json()["error"]["code"]) == (403, "missing_request_header")
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 403

    r = client.post(f"/api/jobs/{job['id']}/retry", headers=ACTION)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "not_retryable")

    r = client.post(f"/api/jobs/{job['id']}/cancel", headers=ACTION)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.get(f"/api/projects/{project['id']}").json()["status"] == "uploaded"
    r = client.post(f"/api/jobs/{job['id']}/cancel", headers=ACTION)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "not_active")

    r = client.post(f"/api/jobs/{job['id']}/retry", headers=ACTION)
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["attempts"]) == ("queued", 0)
    assert client.get(f"/api/projects/{project['id']}").json()["status"] == "processing"


def test_unknown_ids_are_404(client: TestClient) -> None:
    missing = uuid.uuid4()
    for method, url in [
        ("get", f"/api/projects/{missing}/jobs"),
        ("get", f"/api/projects/{missing}/media"),
        ("get", f"/api/frames/{missing}/image"),
        ("post", f"/api/jobs/{missing}/cancel"),
        ("post", f"/api/jobs/{missing}/retry"),
    ]:
        r = client.request(method, url, headers=ACTION)
        assert r.status_code == 404, url
    assert client.get("/api/frames/not-a-uuid/image").status_code == 422


def test_frame_image_never_serves_paths_outside_media(
    client: TestClient, sessions: Sessions, settings: Settings, video: Path, tmp_path: Path
) -> None:
    project = _upload(client, video)
    Worker(HANDLERS, settings=settings, sessions=sessions).run_once()
    frame_id = client.get(f"/api/projects/{project['id']}/media").json()["frames"]["preview"][0][
        "id"
    ]
    (tmp_path / "secret.txt").write_text("secret")
    with sessions() as s:  # simulate a corrupted row pointing outside the media root
        s.execute(update(Frame).where(Frame.id == frame_id).values(storage_path="../secret.txt"))
        s.commit()
    r = client.get(f"/api/frames/{frame_id}/image")
    assert r.status_code == 404
    assert b"secret" not in r.content


def test_cross_site_preflight_is_refused(client: TestClient) -> None:
    def preflight(origin: str) -> dict[str, str]:
        return dict(
            client.options(
                f"/api/jobs/{uuid.uuid4()}/cancel",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "x-seehere-request",
                },
            ).headers
        )

    assert (
        preflight("http://localhost:3000").get("access-control-allow-origin")
        == "http://localhost:3000"
    )
    assert "access-control-allow-origin" not in preflight("https://evil.example")
