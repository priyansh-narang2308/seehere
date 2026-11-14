# SeeHere

**Hear what the lecture shows, not just what it says.**
Evidence-grounded audio descriptions for lecture videos. HackGlobal 2026, Track 02: Multimodal and Accessibility.

> Status: **early build (Tasks 01–10).** Implemented so far: health checks, the design system (`/design`), the application shell, the database schema, secure lecture upload, a Postgres-backed job worker with retries, cancellation, crash recovery and 24-hour deletion, media preparation (16 kHz speech audio and one frame per second, with live progress), local speech-to-text with word timings (Whisper), scene and slide change detection with keyframes, and on-screen text (Tesseract OCR) with number normalization. The later analysis stages are not built yet; the Methodology page shows the live build status of each stage. See `docs/PROJECT_ROADMAP.md`. This README states only what works.

## What it will do

A lecturer says "notice this blue line here". A blind or low-vision student can't see which line. SeeHere:

- analyzes the lecture's speech, frames, on-screen text and (optionally) the slide deck
- finds visual information the narration doesn't convey
- links each generated description to inspectable evidence (frame, region, OCR, slide, transcript)
- schedules the descriptions into pauses without talking over the lecturer
- validates real synthesized-audio timing, and lets an instructor review everything before export.

## Local development

Requirements: Docker, Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 20+ with pnpm, ffmpeg, tesseract.

```bash
cp .env.example .env
make db-up                                  # Postgres 16 on 127.0.0.1:5433
cd backend && uv sync && cd ..
cd web && pnpm install && cp ../.env.example .env.local && cd ..
make api                                    # http://localhost:8000/api/health  (docs: /api/docs)
make worker                                 # background jobs (media preparation, speech-to-text, scene detection, OCR, deletion)
make web                                    # http://localhost:3000  (design system: /design)
make check                                  # lint + typecheck + tests
```

## Documentation

- `docs/ARCHITECTURE.md`: system design
- `docs/ARCHITECTURE_DECISIONS.md`: ADRs
- `docs/DESIGN_SYSTEM.md`: tokens, components, verification states, accessibility checks
- `docs/PROJECT_ROADMAP.md`: 35 tasks, priorities, critical path
- `docs/TASK_LOG.md`: what was done and tested
- `docs/VULTR_RESEARCH_AND_ARCHITECTURE.md`: Vultr services, plans, pricing evidence
- `docs/HACKATHON_REQUIREMENTS.md`: confirmed rules and open questions
- `docs/DEPENDENCIES_AND_LICENSES.md`

## Honesty notes

SeeHere does not certify WCAG compliance. OCR can corroborate quoted text and numbers; it cannot prove that a description of a chart is semantically correct. Existing tools (Microsoft's open-source AI audio descriptions, commercial AI audio-description products) are acknowledged competitors.
