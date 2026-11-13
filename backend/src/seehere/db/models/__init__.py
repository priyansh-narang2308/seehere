"""All ORM models. Importing this package registers every table on `Base.metadata`."""

from seehere.db.models.analysis import (
    Frame,
    OcrRegion,
    ReferenceLink,
    Slide,
    TranscriptSegment,
    TranscriptWord,
    VisualUnit,
)
from seehere.db.models.core import Job, MediaAsset, Project
from seehere.db.models.descriptions import (
    AudioClip,
    DescriptionCue,
    Evidence,
    ExportArtifact,
    ReviewDecision,
    SchedulePlacement,
    ScheduleRun,
    VerificationEvent,
)

__all__ = [
    "AudioClip",
    "DescriptionCue",
    "Evidence",
    "ExportArtifact",
    "Frame",
    "Job",
    "MediaAsset",
    "OcrRegion",
    "Project",
    "ReferenceLink",
    "ReviewDecision",
    "SchedulePlacement",
    "ScheduleRun",
    "Slide",
    "TranscriptSegment",
    "TranscriptWord",
    "VerificationEvent",
    "VisualUnit",
]
