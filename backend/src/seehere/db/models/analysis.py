"""What the pipeline observes: speech, frames, slides, on-screen text, visuals and references."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from seehere.db.base import Base, CreatedAt, UUIDPrimaryKey, str_enum
from seehere.db.enums import ReferenceStatus, VisualKind

# Region boxes are normalized to the frame: 0..1 from the top-left corner.
_BOX_CHECK = (
    "(x IS NULL AND y IS NULL AND w IS NULL AND h IS NULL) OR "
    "(x >= 0 AND y >= 0 AND w > 0 AND h > 0 AND x + w <= 1.0001 AND y + h <= 1.0001)"
)


class TranscriptSegment(UUIDPrimaryKey, Base):
    __tablename__ = "transcript_segment"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_asset.id", ondelete="CASCADE")
    )
    idx: Mapped[int] = mapped_column(Integer)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("media_asset_id", "idx"),
        CheckConstraint("start_s >= 0 AND end_s >= start_s", name="time_order"),
    )


class TranscriptWord(UUIDPrimaryKey, Base):
    """One spoken word with timings. Pauses between words become description windows."""

    __tablename__ = "transcript_word"

    segment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transcript_segment.id", ondelete="CASCADE"), index=True
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_asset.id", ondelete="CASCADE")
    )
    # position within the whole transcript
    idx: Mapped[int] = mapped_column(Integer)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("media_asset_id", "idx"),
        CheckConstraint("start_s >= 0 AND end_s >= start_s", name="time_order"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence"),
        Index("ix_transcript_word_media_time", "media_asset_id", "start_s"),
    )


class Frame(UUIDPrimaryKey, Base):
    __tablename__ = "frame"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_asset.id", ondelete="CASCADE")
    )
    t_s: Mapped[float] = mapped_column(Float)
    storage_path: Mapped[str] = mapped_column(String(512), unique=True)
    is_keyframe: Mapped[bool] = mapped_column(Boolean, default=False)
    scene_index: Mapped[int | None] = mapped_column(Integer)
    phash: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (
        UniqueConstraint("media_asset_id", "t_s"),
        CheckConstraint("t_s >= 0", name="time_positive"),
    )


class Slide(UUIDPrimaryKey, Base):
    """A page of an uploaded slide deck, optionally aligned to the frame where it appears."""

    __tablename__ = "slide"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_asset.id", ondelete="CASCADE")
    )
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    aligned_frame_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("frame.id", ondelete="SET NULL"), index=True
    )
    alignment_score: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("media_asset_id", "page_number"),
        CheckConstraint("page_number >= 1", name="page_positive"),
    )


class OcrRegion(UUIDPrimaryKey, Base):
    __tablename__ = "ocr_region"

    frame_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("frame.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    w: Mapped[float] = mapped_column(Float)
    h: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        CheckConstraint(_BOX_CHECK, name="box"),
    )


class VisualUnit(UUIDPrimaryKey, CreatedAt, Base):
    """One meaningful thing on screen (a chart, a labelled diagram part, an equation...)."""

    __tablename__ = "visual_unit"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    frame_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("frame.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[VisualKind] = mapped_column(str_enum(VisualKind, "visual_kind"))
    label: Mapped[str] = mapped_column(Text)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    w: Mapped[float | None] = mapped_column(Float)
    h: Mapped[float | None] = mapped_column(Float)
    t_start_s: Mapped[float] = mapped_column(Float)
    t_end_s: Mapped[float] = mapped_column(Float)
    # 0 = never mentioned in speech, 1 = fully said aloud (seen-versus-said, Task 13).
    coverage_score: Mapped[float | None] = mapped_column(Float)
    priority: Mapped[float | None] = mapped_column(Float)
    # provider/model that produced it
    source: Mapped[str] = mapped_column(String(100))

    __table_args__ = (
        CheckConstraint(_BOX_CHECK, name="box"),
        CheckConstraint("t_start_s >= 0 AND t_end_s >= t_start_s", name="time_order"),
        CheckConstraint(
            "coverage_score IS NULL OR coverage_score BETWEEN 0 AND 1", name="coverage"
        ),
    )


class ReferenceLink(UUIDPrimaryKey, CreatedAt, Base):
    """A spoken pointer ("this blue line here") and the visual it most likely refers to."""

    __tablename__ = "reference_link"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    phrase: Mapped[str] = mapped_column(Text)
    start_word_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transcript_word.id", ondelete="CASCADE"), index=True
    )
    end_word_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transcript_word.id", ondelete="CASCADE"), index=True
    )
    t_s: Mapped[float] = mapped_column(Float)
    visual_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visual_unit.id", ondelete="SET NULL"), index=True
    )
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[ReferenceStatus] = mapped_column(str_enum(ReferenceStatus, "reference_status"))

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        # A "linked" reference must point at a visual.
        CheckConstraint(
            "status <> 'linked' OR visual_unit_id IS NOT NULL", name="linked_has_target"
        ),
    )
