"""Database integrity rules, exercised against real Postgres (rolled back after each test)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from seehere.db.enums import (
    CheckResult,
    DescriptionMode,
    DescriptionVariant,
    EvidenceKind,
    ExportKind,
    JobStatus,
    MediaKind,
    ProjectStatus,
    ReferenceStatus,
    ReviewAction,
    ReviewStatus,
    ScheduleStatus,
    SolverKind,
    VerificationState,
    VisualKind,
)
from seehere.db.models import (
    AudioClip,
    DescriptionCue,
    Evidence,
    ExportArtifact,
    Frame,
    Job,
    MediaAsset,
    OcrRegion,
    Project,
    ReferenceLink,
    ReviewDecision,
    SchedulePlacement,
    ScheduleRun,
    TranscriptSegment,
    TranscriptWord,
    VerificationEvent,
    VisualUnit,
)

SHA = hashlib.sha256(b"x").hexdigest()


def _project(db: Session, **kw: object) -> Project:
    p = Project(title="Lecture 7", rights_confirmed_at=datetime.now(UTC), **kw)
    db.add(p)
    db.flush()
    return p


def _media(db: Session, project: Project) -> MediaAsset:
    m = MediaAsset(
        project=project,
        kind=MediaKind.SOURCE_VIDEO,
        original_filename="lecture.mp4",
        storage_path=f"projects/{project.id}/source.mp4",
        mime_type="video/mp4",
        size_bytes=1024,
        sha256=SHA,
        duration_s=12.5,
    )
    db.add(m)
    db.flush()
    return m


def _frame(db: Session, media: MediaAsset, t: float = 1.0) -> Frame:
    f = Frame(media_asset_id=media.id, t_s=t, storage_path=f"frames/{media.id}/{t}.jpg")
    db.add(f)
    db.flush()
    return f


def _cue(db: Session, project: Project) -> DescriptionCue:
    c = DescriptionCue(project_id=project.id, text_short="A rising blue line.", anchor_t_s=2.0)
    db.add(c)
    db.flush()
    return c


def _rejects(db: Session, obj: object) -> None:
    """Adding `obj` must violate a database constraint."""
    with db.begin_nested():
        db.add(obj)
        with pytest.raises((IntegrityError, StatementError)):
            db.flush()


def test_defaults_and_server_timestamps(db: Session) -> None:
    project = _project(db)
    job = Job(project_id=project.id, kind="process_project", idempotency_key=f"p:{project.id}")
    db.add(job)
    db.flush()
    db.refresh(project)
    db.refresh(job)
    assert project.status is ProjectStatus.UPLOADED
    assert project.created_at is not None and project.created_at.tzinfo is not None
    assert job.status is JobStatus.QUEUED
    assert (job.progress, job.attempts, job.max_attempts) == (0.0, 0, 3)
    assert job.payload == {} and job.cancel_requested is False


def test_deleting_a_project_cascades_in_the_database(db: Session) -> None:
    project = _project(db)
    media = _media(db, project)
    frame = _frame(db, media)
    cue = _cue(db, project)
    db.add(Evidence(cue_id=cue.id, kind=EvidenceKind.FRAME, frame_id=frame.id))
    db.flush()
    # A raw DELETE proves ON DELETE CASCADE in the schema, not ORM-side cascading.
    db.execute(delete(Project).where(Project.id == project.id))
    db.expunge_all()
    for model in (MediaAsset, Frame, DescriptionCue, Evidence):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def test_text_enums_are_enforced_by_the_database(db: Session) -> None:
    project = _project(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("UPDATE project SET status = 'bogus' WHERE id = :id"), {"id": project.id})


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(
            lambda db: Project(title="   ", rights_confirmed_at=datetime.now(UTC)), id="blank-title"
        ),
        pytest.param(lambda db: Project(title="x"), id="no-rights-confirmation"),
    ],
)
def test_project_rules(db: Session, make: object) -> None:
    _rejects(db, make(db))  # type: ignore[operator]


def test_media_rules(db: Session) -> None:
    project = _project(db)
    base = dict(
        project_id=project.id,
        kind=MediaKind.SOURCE_VIDEO,
        original_filename="a.mp4",
        mime_type="video/mp4",
    )
    _rejects(db, MediaAsset(**base, storage_path="a", size_bytes=0, sha256=SHA))
    _rejects(db, MediaAsset(**base, storage_path="b", size_bytes=1, sha256="NOT-HEX"))
    _rejects(db, MediaAsset(**base, storage_path="c", size_bytes=1, sha256=SHA, duration_s=-1))


def test_job_rules(db: Session) -> None:
    project = _project(db)
    db.add(Job(project_id=project.id, kind="k", idempotency_key="same"))
    db.flush()
    _rejects(db, Job(project_id=project.id, kind="k", idempotency_key="same"))
    _rejects(db, Job(project_id=project.id, kind="k", idempotency_key="p", progress=1.5))


def test_regions_must_be_normalized_boxes(db: Session) -> None:
    frame = _frame(db, _media(db, _project(db)))
    ok = OcrRegion(frame_id=frame.id, text="42", confidence=0.9, x=0.1, y=0.2, w=0.3, h=0.1)
    db.add(ok)
    db.flush()
    _rejects(db, OcrRegion(frame_id=frame.id, text="x", confidence=0.9, x=0.9, y=0, w=0.5, h=0.1))
    _rejects(db, OcrRegion(frame_id=frame.id, text="x", confidence=1.5, x=0, y=0, w=0.1, h=0.1))


def test_evidence_must_cite_its_source(db: Session) -> None:
    cue = _cue(db, _project(db))
    _rejects(db, Evidence(cue_id=cue.id, kind=EvidenceKind.FRAME))
    _rejects(db, Evidence(cue_id=cue.id, kind=EvidenceKind.TRANSCRIPT_SPAN))


def test_linked_reference_needs_a_target(db: Session) -> None:
    project = _project(db)
    media = _media(db, project)
    seg = TranscriptSegment(media_asset_id=media.id, idx=0, start_s=0, end_s=1, text="this")
    db.add(seg)
    db.flush()
    word = TranscriptWord(
        segment_id=seg.id, media_asset_id=media.id, idx=0, start_s=0, end_s=0.4, text="this"
    )
    db.add(word)
    db.flush()
    ref = dict(
        project_id=project.id, phrase="this", start_word_id=word.id, end_word_id=word.id, t_s=0.2
    )
    _rejects(db, ReferenceLink(**ref, confidence=0.9, status=ReferenceStatus.LINKED))
    db.add(ReferenceLink(**ref, confidence=0.2, status=ReferenceStatus.AMBIGUOUS))
    db.flush()


def test_inserted_pause_needs_a_reason(db: Session) -> None:
    project = _project(db)
    cue = _cue(db, project)
    run = ScheduleRun(
        project_id=project.id,
        solver=SolverKind.CP_SAT,
        mode=DescriptionMode.EXTENDED,
        status=ScheduleStatus.SUCCEEDED,
    )
    db.add(run)
    db.flush()
    placement = dict(run_id=run.id, cue_id=cue.id, variant=DescriptionVariant.SHORT)
    _rejects(db, SchedulePlacement(**placement, start_s=1, end_s=2, inserted_pause_s=1.5))
    _rejects(db, SchedulePlacement(**placement, start_s=2, end_s=1))
    db.add(
        SchedulePlacement(
            **placement, start_s=1, end_s=2, inserted_pause_s=1.5, pause_reason="chart has no gap"
        )
    )
    db.flush()


def test_full_evidence_chain_round_trips(db: Session) -> None:
    """Every table in one realistic lineage: speech + frame + OCR → visual → cue → outputs."""
    project = _project(db)
    media = _media(db, project)
    seg = TranscriptSegment(
        media_asset_id=media.id, idx=0, start_s=1.0, end_s=2.0, text="notice this"
    )
    db.add(seg)
    db.flush()
    words = [
        TranscriptWord(
            segment_id=seg.id,
            media_asset_id=media.id,
            idx=i,
            start_s=1 + i * 0.4,
            end_s=1.3 + i * 0.4,
            text=w,
            confidence=0.95,
        )
        for i, w in enumerate(["notice", "this"])
    ]
    db.add_all(words)
    frame = _frame(db, media, t=1.5)
    ocr = OcrRegion(frame_id=frame.id, text="42", confidence=0.91, x=0.6, y=0.3, w=0.05, h=0.04)
    unit = VisualUnit(
        project_id=project.id,
        frame_id=frame.id,
        kind=VisualKind.CHART,
        label="blue line",
        values={"week_3": 42},
        x=0.1,
        y=0.1,
        w=0.8,
        h=0.6,
        t_start_s=1.0,
        t_end_s=9.0,
        coverage_score=0.1,
        source="test",
    )
    db.add_all([ocr, unit])
    db.flush()
    db.add(
        ReferenceLink(
            project_id=project.id,
            phrase="this",
            start_word_id=words[1].id,
            end_word_id=words[1].id,
            t_s=1.5,
            visual_unit_id=unit.id,
            confidence=0.82,
            status=ReferenceStatus.LINKED,
        )
    )
    cue = DescriptionCue(
        project_id=project.id,
        visual_unit_id=unit.id,
        text_short="The blue line peaks at 42 in week 3.",
        anchor_t_s=1.5,
    )
    db.add(cue)
    db.flush()
    db.add_all(
        [
            Evidence(cue_id=cue.id, kind=EvidenceKind.VISUAL_UNIT, visual_unit_id=unit.id),
            Evidence(cue_id=cue.id, kind=EvidenceKind.OCR_REGION, ocr_region_id=ocr.id),
            Evidence(
                cue_id=cue.id,
                kind=EvidenceKind.TRANSCRIPT_SPAN,
                start_word_id=words[0].id,
                end_word_id=words[1].id,
            ),
            VerificationEvent(
                cue_id=cue.id,
                claim="42",
                check_name="number_match",
                result=CheckResult.PASS,
                resulting_state=VerificationState.VERIFIED_TEXT_MATCH,
                detail={"ocr_region": str(ocr.id)},
            ),
            AudioClip(
                cue_id=cue.id,
                variant=DescriptionVariant.SHORT,
                provider="test",
                voice="v",
                text=cue.text_short,
                storage_path=f"audio/{cue.id}.wav",
                duration_s=2.1,
                sample_rate=24000,
                sha256=SHA,
            ),
            ReviewDecision(cue_id=cue.id, action=ReviewAction.APPROVE),
        ]
    )
    run = ScheduleRun(
        project_id=project.id,
        solver=SolverKind.GREEDY,
        mode=DescriptionMode.STANDARD,
        status=ScheduleStatus.SUCCEEDED,
    )
    db.add(run)
    db.flush()
    db.add_all(
        [
            SchedulePlacement(
                run_id=run.id,
                cue_id=cue.id,
                variant=DescriptionVariant.SHORT,
                start_s=2.1,
                end_s=4.2,
            ),
            ExportArtifact(
                project_id=project.id,
                schedule_run_id=run.id,
                kind=ExportKind.WEBVTT,
                storage_path=f"exports/{uuid.uuid4()}.vtt",
                size_bytes=120,
                sha256=SHA,
            ),
        ]
    )
    cue.verification_state = VerificationState.VERIFIED_TEXT_MATCH
    cue.review_status = ReviewStatus.APPROVED
    db.flush()
    db.expunge_all()

    loaded = db.get(DescriptionCue, cue.id)
    assert loaded is not None
    assert {e.kind for e in loaded.evidence} == {
        EvidenceKind.VISUAL_UNIT,
        EvidenceKind.OCR_REGION,
        EvidenceKind.TRANSCRIPT_SPAN,
    }
    assert loaded.verification_state is VerificationState.VERIFIED_TEXT_MATCH
    assert db.scalar(select(func.count()).select_from(SchedulePlacement)) == 1
