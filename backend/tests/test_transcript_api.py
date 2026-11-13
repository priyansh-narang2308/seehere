"""GET /api/projects/{id}/transcript after the real pipeline ran on recorded speech."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from speech_clip import SpeechClip, make_speech_clip, make_speech_video
from sqlalchemy.orm import Session, sessionmaker

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.db.session import get_db
from seehere.jobs.worker import Worker
from seehere.pipeline import HANDLERS

Sessions = sessionmaker[Session]


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> SpeechClip:
    return make_speech_clip(tmp_path_factory.mktemp("speech"))


@pytest.fixture(scope="module")
def video(clip: SpeechClip, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_speech_video(clip, tmp_path_factory.mktemp("video") / "lecture.mp4")


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


def test_transcript_round_trip(
    client: TestClient, sessions: Sessions, settings: Settings, video: Path, clip: SpeechClip
) -> None:
    r = client.post(
        "/api/projects",
        content=video.read_bytes(),
        headers={
            "X-SeeHere-Title": quote("Lecture"),
            "X-SeeHere-Filename": "lecture.mp4",
            "X-SeeHere-Rights-Confirmed": "true",
        },
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert client.get(f"/api/projects/{pid}/transcript").json() == {
        "available": False,
        "provider": None,
        "language": None,
        "duration_s": None,
        "word_count": 0,
        "segments": [],
    }

    worker = Worker(HANDLERS, settings=settings, sessions=sessions)
    while worker.run_once():
        pass

    body = client.get(f"/api/projects/{pid}/transcript").json()
    assert body["available"] is True
    assert (body["provider"], body["language"]) == ("faster-whisper:small.en", "en")
    assert body["duration_s"] == pytest.approx(clip.duration_s, abs=0.1)
    words = [w for s in body["segments"] for w in s["words"]]
    assert body["word_count"] == len(words) > 10
    assert "bar chart on the left" in " ".join(s["text"] for s in body["segments"]).lower()
    assert [w["start_s"] for w in words] == sorted(w["start_s"] for w in words)
    assert set(words[0]) == {"text", "start_s", "end_s", "confidence"}
    assert [j["label"] for j in client.get(f"/api/projects/{pid}/jobs").json()["jobs"]] == [
        "Media preparation",
        "Speech-to-text",
    ]


def test_unknown_project_is_404(client: TestClient) -> None:
    assert client.get(f"/api/projects/{uuid.uuid4()}/transcript").status_code == 404
