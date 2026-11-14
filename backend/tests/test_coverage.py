"""Seen versus said: scoring rules, then the coverage.score job on real visual units from a
rendered lecture video, with transcript words written where speech-to-text would put them."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pipeline_project import add_project, run_jobs, say
from slide_images import make_deck_video
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from seehere.api.main import app
from seehere.core.config import Settings, get_settings
from seehere.db.enums import JobStatus, VisualKind
from seehere.db.models import Job, VisualUnit
from seehere.db.session import get_db
from seehere.text.words import content_words, join_words, spoken_numbers
from seehere.vision.coverage import JOB_KIND, score_unit

Sessions = sessionmaker[Session]
UNITS_CHAIN = ("media.prepare", "scenes.detect", "ocr.extract", "visual.analyze")


# --- scoring ---


def test_spoken_numbers_as_digits_and_words() -> None:
    said = spoken_numbers("revenue rose twelve point five percent to 3.2 million, up from 2,021")
    assert said == [Decimal("3.2") * 10**6, Decimal(2021), Decimal("12.5")]


def test_numbers_split_across_transcript_words_are_rejoined() -> None:
    text = join_words(["revenue", "rose", "12", ".5%.", "to", "3", ",200", "units"])
    assert text == "revenue rose 12.5%. to 3,200 units"
    assert score_unit(VisualKind.CHART, "Rose 12.5%", text).coverage == 1.0


def test_content_words_skip_stop_words_and_fold_plurals() -> None:
    assert content_words("The engineers and the categories of it") == {"engineer", "category"}
    assert content_words("lines boxes values class analysis") == {
        "line",
        "box",
        "value",
        "class",
        "analysis",
    }


def test_fully_said_unit_has_full_coverage_and_no_priority() -> None:
    s = score_unit(
        VisualKind.TEXT_BLOCK,
        "Revenue rose 12.5% to $3.2M",
        "so revenue rose twelve point five percent to three point two million dollars",
    )
    assert (s.coverage, s.priority, s.unsaid) == (1.0, 0.0, [])


def test_partly_said_unit_lists_what_was_missed() -> None:
    s = score_unit(VisualKind.CHART, "Revenue rose 12.5% to $3.2M", "revenue went up 12.5 percent")
    # words: revenue (said), rose (not); numbers count double: 12.5% (said), $3.2M (not)
    assert s.coverage == pytest.approx((1 + 2) / (2 + 4), abs=1e-4)
    assert s.priority == pytest.approx(1 - s.coverage, abs=1e-4)  # charts weigh 1.0
    assert s.said == ["revenue", "12.5%"] and s.unsaid == ["rose", "$3.2M"]


def test_rounded_and_misread_numbers_still_match() -> None:
    assert score_unit(VisualKind.TABLE, "Margin 41.7%", "margin of 41.66 percent").coverage == 1.0
    assert score_unit(VisualKind.TABLE, "Total 1O0", "a total of one hundred").coverage == 1.0
    assert score_unit(VisualKind.TABLE, "Margin 41.7%", "margin of 42 percent").coverage < 1.0


def test_unsaid_units_are_prioritized_by_kind() -> None:
    silent = {k: score_unit(k, "Quarterly revenue 12.5%", "") for k in VisualKind}
    assert all(s.coverage == 0.0 for s in silent.values())
    ranked = sorted(silent, key=lambda k: -silent[k].priority)
    assert ranked[:2] == [VisualKind.CHART, VisualKind.TABLE]
    assert silent[VisualKind.TEXT_BLOCK].priority < silent[VisualKind.DIAGRAM].priority
    assert score_unit(VisualKind.CHART, "", "anything").coverage == 0.0


# --- job ---


@pytest.fixture(scope="module")
def deck(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_deck_video(tmp_path_factory.mktemp("coverage"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(media_dir=tmp_path / "media", job_heartbeat_interval_s=0.2)


def _scores(sessions: Sessions, pid: uuid.UUID) -> dict[tuple[float, str], VisualUnit]:
    with sessions() as s:
        units = s.scalars(select(VisualUnit).where(VisualUnit.project_id == pid))
        return {(u.t_start_s, u.label): u for u in units}


def test_job_scores_each_appearance_against_its_own_window(
    sessions: Sessions, settings: Settings, deck: Path
) -> None:
    pid = add_project(sessions, settings, deck)
    run_jobs(sessions, settings, (*UNITS_CHAIN, JOB_KIND))
    with sessions() as s:  # no transcript yet: the job finishes without scores
        job = s.scalars(select(Job).where(Job.project_id == pid, Job.kind == JOB_KIND)).one()
        assert job.status is JobStatus.SUCCEEDED
    assert all(u.coverage_score is None for u in _scores(sessions, pid).values())

    # Spoken while slide 1 is first shown (0-5 s); slide 1 comes back at 9-12 s.
    spoken = "this quarter revenue rose twelve point five percent"
    say(sessions, pid, [(0.5 + 0.4 * i, w) for i, w in enumerate(spoken.split())])
    run_jobs(sessions, settings, (JOB_KIND,))

    units = _scores(sessions, pid)
    revenue = units[(0.0, "Revenue rose 12.5% to $3.2M")]
    assert revenue.coverage_score == pytest.approx(4 / 6, abs=1e-3)
    assert revenue.values["said"] == ["revenue", "rose", "12.5%"]
    assert revenue.values["unsaid"] == ["$3.2M"]
    margin = units[(0.0, "Operating margin 41.7% in 2022")]
    assert margin.coverage_score == 0.0
    assert margin.priority == pytest.approx(0.6)  # text block weight
    # The revisit (9-12 s, window 4-17 s) heard none of it.
    assert units[(9.0, "Revenue rose 12.5% to $3.2M")].coverage_score == 0.0
    # Slide 2 (5-9 s, window 0-14 s) shares no words with what was said.
    assert units[(5.0, "Hire 3 engineers by March")].coverage_score == 0.0

    body = _get(sessions, settings, f"/api/projects/{pid}/visuals")
    assert body["available"] and body["scored"]
    priorities = [u["priority"] for u in body["units"]]
    assert priorities == sorted(priorities, reverse=True)  # most in need of description first
    last = body["units"][-1]
    assert (last["label"], last["t_start_s"], last["unsaid"]) == (revenue.label, 0.0, ["$3.2M"])
    assert last["kind"] == "text_block" and last["source"] == "ocr" and last["x"] is not None


def test_visuals_api_before_analysis(sessions: Sessions, settings: Settings, deck: Path) -> None:
    pid = add_project(sessions, settings, deck)
    assert _get(sessions, settings, f"/api/projects/{pid}/visuals") == {
        "available": False,
        "scored": False,
        "units": [],
    }
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get(f"/api/projects/{uuid.uuid4()}/visuals").status_code == 404


def _get(sessions: Sessions, settings: Settings, url: str) -> dict[str, Any]:
    def db() -> Iterator[Session]:
        with sessions() as s:
            yield s

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = db
    try:
        with TestClient(app) as c:
            r = c.get(url)
            assert r.status_code == 200, r.text
            body: dict[str, Any] = r.json()
            return body
    finally:
        app.dependency_overrides.clear()
