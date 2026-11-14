"""Coverage and verification report (Task 28): one outcome per visual, with reasons."""

from __future__ import annotations

import uuid
from collections import Counter

from seehere.db.enums import ReviewStatus, VerificationState
from seehere.report.coverage import CueFact, ScheduleFacts, UnitFact, build_report, report_html

V = VerificationState


def _ids(n: int) -> list[uuid.UUID]:
    return [uuid.UUID(int=i + 1) for i in range(n)]


def test_every_visual_gets_one_outcome_with_its_reason() -> None:
    u = _ids(8)
    c = [uuid.UUID(int=100 + i) for i in range(8)]
    units = [UnitFact(u[i], "text_block", f"Item {i}", float(i), i + 2.0, 0.0) for i in range(8)]
    units[0] = UnitFact(u[0], "title", "Said", 0.0, 2.0, 1.0)  # fully said aloud: no cue
    cues = [
        CueFact(c[2], u[2], "described", V.VERIFIED_TEXT_MATCH, ReviewStatus.PENDING),
        CueFact(c[3], u[3], "paused", V.CORROBORATED, ReviewStatus.PENDING),
        CueFact(c[4], u[4], "no room", V.UNCERTAIN, ReviewStatus.PENDING),
        CueFact(c[5], u[5], "held", V.NEEDS_REVIEW, ReviewStatus.PENDING),
        CueFact(c[6], u[6], "rejected", V.NEEDS_REVIEW, ReviewStatus.REJECTED),
        CueFact(c[7], u[7], "approved", V.NEEDS_REVIEW, ReviewStatus.APPROVED),
    ]
    sched = ScheduleFacts(
        scheduled=True,
        standard={c[2], c[7]},
        extended={c[3]: (1.2, "Item 3 is on screen while the speaker talks")},
        skipped={c[4]: "the longest free pause (0.8 s) is too short"},
        skipped_extended={c[4]: "needs a 2.0 s pause; only 0.5 s of the 1.0 s budget is left"},
        held={c[5]},
        timing={"standard": {"solver": "cp_sat", "round": 2, "check": {"status": "fits"}}},
    )
    report = build_report(units, cues, sched, Counter({"pass": 3, "fail": 1}))

    outcome = {i["label"]: (i["outcome"], i["reason"]) for i in report["items"]}
    assert outcome["Said"] == ("said_aloud", "every line on it was said aloud")
    assert outcome["Item 1"][0] == "repeat"  # no cue but not fully said: described elsewhere
    assert outcome["Item 2"] == ("described", None)
    assert outcome["Item 3"] == ("described_extended", sched.extended[c[3]][1])
    assert outcome["Item 4"] == ("skipped", sched.skipped_extended[c[4]])
    assert outcome["Item 5"][0] == "held_for_review"
    assert outcome["Item 6"][0] == "rejected"
    assert outcome["Item 7"][0] == "described"  # approved by the instructor, so voiced

    summary = report["summary"]
    assert summary["visual_units"] == 8 and summary["descriptions"] == 6
    assert summary["uncovered"] == 3  # skipped, held, rejected
    assert report["verification"] == {
        "verified_text_match": 1,
        "corroborated": 1,
        "uncertain": 1,
        "needs_review": 3,
    }
    assert report["review"] == {"pending": 4, "approved": 1, "rejected": 1}
    assert report["checks"] == {"pass": 3, "fail": 1, "inconclusive": 0}
    assert "not complete fact-checking" in report["notice"]

    page = report_html("Week <1>", report)
    assert "Week &lt;1&gt;" in page and "Not described: rejected by the instructor" in page
    assert "audio timing fits" in page


def test_before_scheduling_described_visuals_are_not_scheduled() -> None:
    u, c = _ids(1)[0], uuid.UUID(int=9)
    report = build_report(
        [UnitFact(u, "chart", "Chart", 0.0, 4.0, 0.2)],
        [CueFact(c, u, "A chart", V.UNCERTAIN, ReviewStatus.PENDING)],
        ScheduleFacts(),
        Counter(),
    )
    assert report["items"][0]["outcome"] == "not_scheduled"
    assert report["summary"]["uncovered"] == 1
