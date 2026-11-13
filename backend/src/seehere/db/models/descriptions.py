"""Descriptions, their evidence and verification, scheduling, audio, review and exports."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from seehere.db.base import Base, CreatedAt, Timestamps, UUIDPrimaryKey, str_enum
from seehere.db.enums import (
    CheckResult,
    DescriptionMode,
    DescriptionVariant,
    EvidenceKind,
    ExportKind,
    ReviewAction,
    ReviewStatus,
    ScheduleStatus,
    SolverKind,
    VerificationState,
)


class DescriptionCue(UUIDPrimaryKey, Timestamps, Base):
    """One audio description with short/medium/long wordings of the same evidence."""

    __tablename__ = "description_cue"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    visual_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visual_unit.id", ondelete="SET NULL"), index=True
    )
    text_short: Mapped[str] = mapped_column(Text)
    text_medium: Mapped[str | None] = mapped_column(Text)
    text_long: Mapped[str | None] = mapped_column(Text)
    anchor_t_s: Mapped[float] = mapped_column(Float)  # when the visual becomes relevant
    priority: Mapped[float] = mapped_column(Float, default=0.5, server_default=text("0.5"))
    # Starts at needs_review; only claim verification (Task 17) can raise it.
    verification_state: Mapped[VerificationState] = mapped_column(
        str_enum(VerificationState, "verification_state"),
        default=VerificationState.NEEDS_REVIEW,
        server_default=VerificationState.NEEDS_REVIEW.value,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        str_enum(ReviewStatus, "review_status"),
        default=ReviewStatus.PENDING,
        server_default=ReviewStatus.PENDING.value,
    )

    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="cue", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("length(trim(text_short)) > 0", name="short_not_blank"),
        CheckConstraint("anchor_t_s >= 0", name="anchor_positive"),
        CheckConstraint("priority BETWEEN 0 AND 1", name="priority_range"),
    )


class Evidence(UUIDPrimaryKey, CreatedAt, Base):
    """One link in a cue's evidence ledger. At least one source reference is required."""

    __tablename__ = "evidence"

    cue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("description_cue.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[EvidenceKind] = mapped_column(str_enum(EvidenceKind, "evidence_kind"))
    frame_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("frame.id", ondelete="CASCADE"), index=True
    )
    ocr_region_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ocr_region.id", ondelete="CASCADE"), index=True
    )
    slide_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("slide.id", ondelete="CASCADE"), index=True
    )
    visual_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visual_unit.id", ondelete="CASCADE"), index=True
    )
    start_word_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transcript_word.id", ondelete="CASCADE"), index=True
    )
    end_word_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transcript_word.id", ondelete="CASCADE"), index=True
    )
    note: Mapped[str | None] = mapped_column(Text)

    cue: Mapped[DescriptionCue] = relationship(back_populates="evidence")

    __table_args__ = (
        CheckConstraint(
            "(kind = 'frame' AND frame_id IS NOT NULL) OR "
            "(kind = 'ocr_region' AND ocr_region_id IS NOT NULL) OR "
            "(kind = 'slide' AND slide_id IS NOT NULL) OR "
            "(kind = 'visual_unit' AND visual_unit_id IS NOT NULL) OR "
            "(kind = 'transcript_span' AND start_word_id IS NOT NULL AND end_word_id IS NOT NULL)",
            name="kind_has_source",
        ),
    )


class VerificationEvent(UUIDPrimaryKey, CreatedAt, Base):
    """One check of one claim in a cue (e.g. "42 appears on screen") and its outcome."""

    __tablename__ = "verification_event"

    cue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("description_cue.id", ondelete="CASCADE"), index=True
    )
    claim: Mapped[str] = mapped_column(Text)
    check_name: Mapped[str] = mapped_column(String(50))  # e.g. number_match, quote_match
    result: Mapped[CheckResult] = mapped_column(str_enum(CheckResult, "check_result"))
    resulting_state: Mapped[VerificationState] = mapped_column(
        str_enum(VerificationState, "verification_state")
    )
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class ScheduleRun(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "schedule_run"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    solver: Mapped[SolverKind] = mapped_column(str_enum(SolverKind, "solver_kind"))
    mode: Mapped[DescriptionMode] = mapped_column(str_enum(DescriptionMode, "description_mode"))
    status: Mapped[ScheduleStatus] = mapped_column(str_enum(ScheduleStatus, "schedule_status"))
    round: Mapped[int] = mapped_column(Integer, default=1)  # re-solve round after TTS timing
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    duration_ms: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (CheckConstraint("round >= 1", name="round_positive"),)


class SchedulePlacement(UUIDPrimaryKey, Base):
    """Where a cue plays in one schedule run, and any pause inserted for it (extended mode)."""

    __tablename__ = "schedule_placement"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_run.id", ondelete="CASCADE"), index=True
    )
    cue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("description_cue.id", ondelete="CASCADE"), index=True
    )
    variant: Mapped[DescriptionVariant] = mapped_column(
        str_enum(DescriptionVariant, "description_variant")
    )
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    inserted_pause_s: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    pause_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("run_id", "cue_id"),
        CheckConstraint("start_s >= 0 AND end_s > start_s", name="time_order"),
        CheckConstraint("inserted_pause_s >= 0", name="pause_positive"),
        # Every inserted pause must say why.
        CheckConstraint(
            "inserted_pause_s = 0 OR pause_reason IS NOT NULL", name="pause_has_reason"
        ),
    )


class AudioClip(UUIDPrimaryKey, CreatedAt, Base):
    """Synthesized speech for one cue wording. `duration_s` is measured from the file."""

    __tablename__ = "audio_clip"

    cue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("description_cue.id", ondelete="CASCADE"), index=True
    )
    variant: Mapped[DescriptionVariant] = mapped_column(
        str_enum(DescriptionVariant, "description_variant")
    )
    provider: Mapped[str] = mapped_column(String(100))
    voice: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)  # exact text spoken, to detect stale audio
    storage_path: Mapped[str] = mapped_column(String(512), unique=True)
    duration_s: Mapped[float] = mapped_column(Float)
    sample_rate: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint("duration_s > 0", name="duration_positive"),
        CheckConstraint("sample_rate > 0", name="sample_rate_positive"),
    )


class ReviewDecision(UUIDPrimaryKey, CreatedAt, Base):
    """Audit trail of instructor actions on a cue."""

    __tablename__ = "review_decision"

    cue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("description_cue.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[ReviewAction] = mapped_column(str_enum(ReviewAction, "review_action"))
    previous_text: Mapped[str | None] = mapped_column(Text)
    new_text: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("action <> 'edit' OR new_text IS NOT NULL", name="edit_has_text"),
    )


class ExportArtifact(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "export_artifact"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    schedule_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schedule_run.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[ExportKind] = mapped_column(str_enum(ExportKind, "export_kind"))
    storage_path: Mapped[str] = mapped_column(String(512), unique=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))

    __table_args__ = (CheckConstraint("size_bytes > 0", name="size_positive"),)
