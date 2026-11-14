"""Instructor review: approve, reject, edit (re-verified) and regenerate; every action is
recorded, re-schedules the lecture, and survives a re-run of the analysis."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pipeline_project import add_project, run_jobs, say
from slide_images import make_deck_video
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.db.enums import JobStatus
from seehere.db.models import Job
from seehere.db.session import get_db
from seehere.describe.generate import queue_descriptions

Sessions = sessionmaker[Session]
FIRST = ("media.prepare", "scenes.detect", "ocr.extract", "visual.analyze")
CHAIN = (
    "coverage.score",
    "references.resolve",
    "descriptions.generate",
    "claims.verify",
    "schedule.plan",
)
H = {"X-SeeHere-Request": "1"}


@pytest.fixture(scope="module")
def deck(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_deck_video(tmp_path_factory.mktemp("review"))


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


def _cue(client: TestClient, pid: object, text: str) -> dict:
    return next(
        c for c in client.get(f"/api/projects/{pid}/cues").json()["cues"] if c["text_short"] == text
    )


def _plan_queued(sessions: Sessions, pid: object) -> bool:
    with sessions() as s:
        job = s.scalars(select(Job).where(Job.project_id == pid, Job.kind == "schedule.plan")).one()
        return job.status is JobStatus.QUEUED


def test_review_actions(
    client: TestClient, sessions: Sessions, settings: Settings, deck: Path
) -> None:
    pid = add_project(sessions, settings, deck)
    run_jobs(sessions, settings, FIRST)
    say(sessions, pid, [(0.5 + 0.3 * i, w) for i, w in enumerate(["hello", "and", "welcome"])])
    run_jobs(sessions, settings, CHAIN)
    cue = _cue(client, pid, "On screen: “Next steps”.")
    url = f"/api/cues/{cue['id']}/review"

    assert client.post(url, json={"action": "approve"}).status_code == 403  # needs the header
    assert (
        client.post(url, json={"action": "edit", "text": "  "}, headers=H).json()["error"]["code"]
        == "invalid_review"
    )

    # An edit with a number that is not on screen: saved, but verified like any text.
    led = client.post(
        url,
        json={"action": "edit", "text": "Next steps: hire 5 engineers.", "note": "clearer"},
        headers=H,
    ).json()
    assert led["cue"]["text_short"] == "Next steps: hire 5 engineers."
    assert (led["cue"]["text_medium"], led["cue"]["text_long"]) == (None, None)
    assert led["cue"]["review_status"] == "approved"
    assert led["cue"]["verification_state"] == "needs_review"
    assert ("5", "fail") in {(c["claim"], c["result"]) for c in led["checks"]}
    assert [(d["action"], d["new_text"], d["note"]) for d in led["decisions"]] == [
        ("edit", "Next steps: hire 5 engineers.", "clearer")
    ]
    assert _plan_queued(sessions, pid)  # re-scheduled
    run_jobs(sessions, settings, ("schedule.plan",))
    plan = client.get(f"/api/projects/{pid}/schedule").json()
    # Approved by a person, so it may be voiced even though a check failed.
    assert all(
        "needs review" not in n["reason"] for n in plan["not_placed"] if n["cue_id"] == cue["id"]
    )

    # Regenerate restores the evidence-built wording and asks for review again.
    led = client.post(url, json={"action": "regenerate"}, headers=H).json()
    assert led["cue"]["text_short"] == "On screen: “Next steps”."
    assert (led["cue"]["review_status"], led["cue"]["verification_state"]) == (
        "pending",
        "verified_text_match",
    )

    # Reject: never voiced.
    client.post(url, json={"action": "reject"}, headers=H)
    run_jobs(sessions, settings, ("schedule.plan",))
    plan = client.get(f"/api/projects/{pid}/schedule").json()
    assert cue["id"] not in {p["cue_id"] for p in plan["placements"]}
    assert [
        d["action"] for d in client.get(f"/api/cues/{cue['id']}/evidence").json()["decisions"]
    ] == [
        "edit",
        "regenerate",
        "reject",
    ]


def test_reviews_survive_a_rerun_of_the_analysis(
    client: TestClient, sessions: Sessions, settings: Settings, deck: Path
) -> None:
    pid = add_project(sessions, settings, deck)
    run_jobs(sessions, settings, FIRST)
    say(sessions, pid, [(0.5, "hello")])
    run_jobs(sessions, settings, CHAIN)
    cue = _cue(client, pid, "On screen: “Hire 3 engineers by March”.")
    client.post(
        f"/api/cues/{cue['id']}/review",
        json={"action": "edit", "text": "Hire 3 engineers by March."},
        headers=H,
    )
    with sessions() as s:  # e.g. a slide deck was added: descriptions are rebuilt
        queue_descriptions(s, pid)
        s.commit()
    run_jobs(sessions, settings, ("descriptions.generate", "claims.verify"))
    again = _cue(client, pid, "Hire 3 engineers by March.")
    assert again["id"] != cue["id"] and again["review_status"] == "approved"
    # Re-verified: the number is on screen, but a plain statement needs a vision model, so it
    # stays "needs review", and is voiced only because an instructor approved it.
    assert again["verification_state"] == "needs_review"
    led = client.get(f"/api/cues/{again['id']}/evidence").json()
    assert [d["action"] for d in led["decisions"]] == ["edit"]
