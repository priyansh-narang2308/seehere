"""Domain vocabularies. Values are stored as text and are part of the API contract."""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class MediaKind(StrEnum):
    SOURCE_VIDEO = "source_video"
    SLIDE_DECK = "slide_deck"
    NORMALIZED_AUDIO = "normalized_audio"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VisualKind(StrEnum):
    CHART = "chart"
    DIAGRAM = "diagram"
    TABLE = "table"
    EQUATION = "equation"
    TEXT_BLOCK = "text_block"
    IMAGE = "image"
    OTHER = "other"


class ReferenceStatus(StrEnum):
    LINKED = "linked"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class DescriptionVariant(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class VerificationState(StrEnum):
    """The four states shown in the UI. Never add one without updating the web app."""

    VERIFIED_TEXT_MATCH = "verified_text_match"
    CORROBORATED = "corroborated"
    UNCERTAIN = "uncertain"
    NEEDS_REVIEW = "needs_review"


class CheckResult(StrEnum):
    PASS = "pass"  # noqa: S105 - not a password
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    REGENERATE = "regenerate"


class EvidenceKind(StrEnum):
    FRAME = "frame"
    OCR_REGION = "ocr_region"
    SLIDE = "slide"
    TRANSCRIPT_SPAN = "transcript_span"
    VISUAL_UNIT = "visual_unit"


class SolverKind(StrEnum):
    GREEDY = "greedy"
    CP_SAT = "cp_sat"


class DescriptionMode(StrEnum):
    STANDARD = "standard"
    EXTENDED = "extended"


class ScheduleStatus(StrEnum):
    SUCCEEDED = "succeeded"
    INFEASIBLE = "infeasible"
    FAILED = "failed"


class ExportKind(StrEnum):
    WEBVTT = "webvtt"
    CUE_AUDIO_ZIP = "cue_audio_zip"
    STANDARD_MP4 = "standard_mp4"
    EXTENDED_MP4 = "extended_mp4"
    TRANSCRIPT_HTML = "transcript_html"
    MANIFEST_JSON = "manifest_json"
    BUNDLE_ZIP = "bundle_zip"
