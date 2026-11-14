"""Speech synthesis job (Task 22): one audio clip per wording the schedules use, with its
duration measured from the file (checked against its slot in Task 23).

A clip is reused while its text, provider and voice are unchanged and its file is intact, so
re-running the pipeline does not re-synthesize (or, with Vultr, pay for) the same speech.
Clips no schedule uses any more are deleted.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
import wave
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from seehere.core.config import Settings
from seehere.db.enums import DescriptionVariant
from seehere.db.models import AudioClip, DescriptionCue, SchedulePlacement, ScheduleRun
from seehere.jobs import queue
from seehere.jobs.errors import PermanentJobError
from seehere.jobs.queue import ClaimedJob
from seehere.jobs.worker import JobContext
from seehere.media.storage import MediaStore, project_dir
from seehere.providers.base import TextToSpeech
from seehere.providers.errors import job_error
from seehere.providers.tts_piper import PiperError, PiperTTS, PiperVoiceMissing
from seehere.providers.tts_vultr import VultrTTS, VultrTTSError
from seehere.schedule.timing import queue_timing_check

log = logging.getLogger("seehere.tts")

JOB_KIND = "speech.synthesize"


def queue_synthesis(session: Session, project_id: uuid.UUID) -> None:
    """Queue (or re-queue) after scheduling. Does not commit."""
    queue.enqueue_or_restart(
        session, project_id=project_id, kind=JOB_KIND, idempotency_key=f"{JOB_KIND}:{project_id}"
    )


def make_tts(settings: Settings) -> TextToSpeech:
    if settings.tts_provider == "vultr":
        if settings.vultr_inference_api_key is None:
            raise PermanentJobError("Vultr text-to-speech is selected but no API key is set.")
        return VultrTTS(
            settings.vultr_inference_api_key,
            base_url=settings.vultr_inference_base_url,
            model=settings.vultr_tts_model,
            voice=settings.vultr_tts_voice,
            timeout_s=settings.vultr_tts_timeout_s,
        )
    return PiperTTS(settings.piper_voice_dir, settings.piper_voice, piper_bin=settings.piper_bin)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _text(cue: DescriptionCue, variant: DescriptionVariant) -> str:
    return {
        DescriptionVariant.SHORT: cue.text_short,
        DescriptionVariant.MEDIUM: cue.text_medium,
        DescriptionVariant.LONG: cue.text_long,
    }[variant] or cue.text_short


def synthesize_speech(ctx: JobContext, job: ClaimedJob) -> None:
    pid = job.project_id
    store = MediaStore(ctx.settings.media_dir)
    tts = make_tts(ctx.settings)
    provider, _, voice = tts.info().name.partition(":")
    voice = getattr(tts, "voice", voice)
    with ctx.session() as s:
        needed = {
            (cue_id, variant)
            for cue_id, variant in s.execute(
                select(SchedulePlacement.cue_id, SchedulePlacement.variant)
                .join(ScheduleRun, SchedulePlacement.run_id == ScheduleRun.id)
                .where(ScheduleRun.project_id == pid)
            )
        }
        cues = {
            c.id: c
            for c in s.scalars(select(DescriptionCue).where(DescriptionCue.project_id == pid))
        }
        existing = list(
            s.scalars(
                select(AudioClip).join(DescriptionCue).where(DescriptionCue.project_id == pid)
            )
        )
        keep: dict[tuple[uuid.UUID, DescriptionVariant], AudioClip] = {}
        for clip in existing:
            key = (clip.cue_id, clip.variant)
            cue = cues.get(clip.cue_id)
            fresh = (
                key in needed
                and cue is not None
                and clip.text == _text(cue, clip.variant)
                and (clip.provider, clip.voice) == (provider, voice)
                and store.resolve(clip.storage_path).is_file()
            )
            if fresh and key not in keep:
                keep[key] = clip
            else:
                path = store.resolve(clip.storage_path)
                path.unlink(missing_ok=True)
                s.delete(clip)
        s.flush()

        todo = sorted(needed - keep.keys(), key=lambda k: (cues[k[0]].anchor_t_s, k[1].value))
        for i, (cue_id, variant) in enumerate(todo):
            ctx.check_cancelled()
            text = _text(cues[cue_id], variant)
            digest = hashlib.sha256(f"{provider}|{voice}|{text}".encode()).hexdigest()[:12]
            rel = f"{project_dir(pid)}/audio/{cue_id}-{variant.value}-{digest}.wav"
            path = store.resolve(rel)
            try:
                out = tts.synthesize(text, path)
            except (PiperVoiceMissing, PiperError) as e:
                raise PermanentJobError(str(e)) from None
            except VultrTTSError as e:
                log.warning("text-to-speech failed for cue %s: %s", cue_id, e)
                raise job_error(e, "Vultr text-to-speech") from None
            s.add(
                AudioClip(
                    cue_id=cue_id,
                    variant=variant,
                    provider=out.provider,
                    voice=out.voice,
                    text=text,
                    storage_path=rel,
                    duration_s=out.duration_ms / 1000,
                    sample_rate=_rate(path),
                    sha256=_sha256(path),
                )
            )
            ctx.progress("synthesize", (i + 1) / len(todo))
        queue_timing_check(s, pid)
        s.commit()
    log.info("project %s: %d clips synthesized, %d reused", pid, len(todo), len(keep))


def _rate(path: Path) -> int:
    with wave.open(str(path), "rb") as w:
        return w.getframerate()
