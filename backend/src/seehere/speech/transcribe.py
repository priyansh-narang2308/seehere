"""Speech-to-text (pipeline stage "speech", job kind `speech.transcribe`).

Runs after media preparation, on its 16 kHz mono WAV, with the local faster-whisper adapter
(the only provider whose word timestamps are TESTED). Stores one `transcript_segment` row per
recognizer segment and one `transcript_word` row per word, times in seconds of the source.

Idempotent: a run replaces every transcript row of the audio asset in one transaction. When
media preparation runs again it replaces the audio asset, which deletes the old transcript
(foreign-key cascade) and re-queues this job.

Cancellation is checked between recognizer segments (about every 30 s of audio).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from seehere.core.config import Settings
from seehere.db.enums import MediaKind
from seehere.db.models import MediaAsset, TranscriptSegment, TranscriptWord
from seehere.jobs import queue
from seehere.jobs.errors import PermanentJobError, RetryableJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.providers.base import SpeechToText
from seehere.providers.stt_faster_whisper import FasterWhisperSTT, ModelUnavailable

log = logging.getLogger("seehere.speech")

JOB_KIND = "speech.transcribe"


def make_stt(settings: Settings) -> FasterWhisperSTT:
    return FasterWhisperSTT(
        settings.local_stt_model,
        compute_type=settings.local_stt_compute_type,
        cpu_threads=settings.local_stt_cpu_threads,
        beam_size=settings.local_stt_beam_size,
        download_root=settings.local_stt_model_dir,
    )


def queue_transcription(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) speech-to-text for a project whose audio was just (re)made.
    Does not commit: the caller commits it with the new audio."""
    queue.enqueue_or_restart(
        session,
        project_id=project_id,
        kind=JOB_KIND,
        idempotency_key=f"{JOB_KIND}:{project_id}",
    )


def _ms_to_s(ms: int) -> float:
    return round(ms / 1000, 3)


def transcribe_speech(ctx: JobContext, job: ClaimedJob) -> None:
    with ctx.session() as s:
        audio = s.scalars(
            select(MediaAsset).where(
                MediaAsset.project_id == job.project_id,
                MediaAsset.kind == MediaKind.NORMALIZED_AUDIO,
            )
        ).first()
        if audio is None:
            raise PermanentJobError("The prepared audio is missing. Run media preparation again.")
        audio_id, audio_rel = audio.id, audio.storage_path
    path = ctx.store.resolve(audio_rel)
    if not path.is_file():
        raise PermanentJobError("The prepared audio is missing. Run media preparation again.")

    stt = make_stt(ctx.settings)
    ctx.progress("model", 0.0)
    try:
        stt.load()
    except ModelUnavailable as exc:
        log.warning("%s", exc)
        raise RetryableJobError("The speech recognition model could not be loaded.") from exc

    ctx.progress("transcribe", 0.05)
    engine: SpeechToText = stt
    try:
        transcript = engine.transcribe(
            path, progress=lambda f: ctx.progress("transcribe", 0.05 + 0.9 * f)
        )
    except ValueError as exc:
        raise PermanentJobError("The prepared audio could not be read.") from exc

    ctx.progress("save", 0.95)
    ctx.check_cancelled()
    word_idx = 0
    with ctx.session() as s:
        s.execute(delete(TranscriptSegment).where(TranscriptSegment.media_asset_id == audio_id))
        for seg_idx, seg in enumerate(transcript.segments):
            row = TranscriptSegment(
                media_asset_id=audio_id,
                idx=seg_idx,
                start_s=_ms_to_s(seg.start_ms),
                end_s=_ms_to_s(seg.end_ms),
                text=seg.text,
            )
            s.add(row)
            s.flush()
            for w in seg.words:
                s.add(
                    TranscriptWord(
                        segment_id=row.id,
                        media_asset_id=audio_id,
                        idx=word_idx,
                        start_s=_ms_to_s(w.start_ms),
                        end_s=_ms_to_s(w.end_ms),
                        text=w.text,
                        confidence=w.confidence,
                    )
                )
                word_idx += 1
        asset = s.get(MediaAsset, audio_id)
        if asset is None:  # media preparation replaced the audio while we ran: try again
            raise RetryableJobError("The audio changed during speech recognition.")
        asset.probe = {
            **(asset.probe or {}),
            "transcript": {
                "provider": transcript.provider,
                "language": transcript.language,
                "segments": len(transcript.segments),
                "words": word_idx,
                **transcript.metadata,
            },
        }
        s.commit()
    log.info(
        "project %s: %d segments, %d words (%s)",
        job.project_id,
        len(transcript.segments),
        word_idx,
        transcript.provider,
    )
    ctx.progress("save", 1.0)
