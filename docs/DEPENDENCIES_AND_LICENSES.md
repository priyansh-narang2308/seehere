# Dependencies and Licences

Our own code is in `backend/src/seehere` and `web/src`. Everything below is a third-party dependency, used unmodified.

## Installed now (Task 01)
| Dependency | Use | Licence |
|---|---|---|
| FastAPI | HTTP API | MIT |
| Uvicorn | ASGI server | BSD-3-Clause |
| Pydantic / pydantic-settings | validation, settings | MIT |
| SQLAlchemy | ORM | MIT |
| psycopg 3 | Postgres driver | LGPL-3.0 (dynamic use) |
| Alembic | migrations | MIT |
| faster-whisper (+ CTranslate2, tokenizers, huggingface_hub, onnxruntime, NumPy) | local speech-to-text | MIT / MIT / Apache-2.0 / Apache-2.0 / MIT / BSD-3-Clause |
| Pillow | frame thumbnails | MIT-CMU (HPND) |
| pypdf | PDF slide text | BSD-3-Clause |
| defusedxml | safe XML parsing (PPTX) | PSF-2.0 |
| jsonschema | validating vision-model output | MIT |
| Whisper `small.en` weights (Systran/faster-whisper-small.en) | STT model, downloaded on first use | MIT |
| httpx | HTTP client | BSD-3-Clause |
| pytest, ruff, mypy | dev tooling | MIT |
| Next.js, React | web | MIT |
| Tailwind CSS | styling | MIT |
| PostgreSQL 16 (Docker image) | database | PostgreSQL Licence |
| FFmpeg / FFprobe (system binary, subprocess) | media | LGPL/GPL depending on build (not linked) |
| Tesseract (system binary) | OCR | Apache-2.0 |

## Added in Task 02
| Dependency | Use | Licence |
|---|---|---|
| @radix-ui/react-dialog, -tabs, -toast, -slot | accessible primitives | MIT |
| class-variance-authority | component variants | Apache-2.0 |
| clsx | class joining | MIT |
| tailwind-merge | class conflict resolution | MIT |
| lucide-react | icons | ISC |
| Inter, JetBrains Mono (via next/font, self-hosted) | typefaces | SIL OFL 1.1 |
| vitest, @vitejs/plugin-react, jsdom | test runner (dev) | MIT |
| @testing-library/react, user-event, jest-dom | component tests (dev) | MIT |
| axe-core | accessibility checks in tests (dev) | MPL-2.0 (unmodified, dev only) |

## Added in Tasks 04–05
| Dependency | Use | Licence |
|---|---|---|
| server-only | keeps server data loaders out of client bundles | MIT |

No new backend packages: upload streaming uses FastAPI/Starlette and the standard library; video inspection calls the existing ffprobe binary.

## Tasks 06–07
No new dependencies. The job queue uses Postgres and SQLAlchemy; media preparation calls the existing FFmpeg/FFprobe binaries.

## Planned (added in their tasks; licence re-checked when added)
OR-Tools (Apache-2.0) · faster-whisper (MIT) + Whisper model weights (MIT) · PySceneDetect (BSD-3) · OpenCV (Apache-2.0) · pypdf (BSD-3, used instead of AGPL PyMuPDF) · defusedxml (PSF) · Piper TTS (`piper-tts`, GPL-3.0 since 1.3; installed as a separate tool with `uv tool install` and run as its own process, never imported or bundled in SeeHere's package) · default voice `en_US-ljspeech-medium`, trained on LJ Speech (public domain).

## Baseline (not part of our product)
microsoft/ai-audio-descriptions (MIT, Copyright (c) 2024 Microsoft; licence checked 2026-11-14) is the comparison baseline (Task 29), pinned at commit `be76687c6cc4ee9667328bcc380d76c1bb95ab94`. `bench/microsoft/run.sh` clones it into `var/baselines/` (git-ignored) with its own virtual environment and runs its GenerateAD CLI unmodified; its code is never copied into SeeHere. Attribution and the full licence: `bench/microsoft/NOTICE.md`. It needs a chargeable Azure Foundry resource (Speech + GPT), which has not been provisioned, so it is currently UNAVAILABLE and reports no numbers.

## Tasks 26–30
No new packages. The report and benchmark use the standard library, SQLAlchemy and the existing number parser. One migration adds the `report_html` and `report_json` export kinds.

## Tasks 31–33
No new packages. Rate limiting, security headers and measurements use the standard library (`resource`, `contextvars`) and FastAPI middleware. One migration adds `job.metrics`.

## Hosted models (Vultr Serverless Inference, used via API)
Model licences are per the Vultr catalog and model cards. `auk` is "evaluation only", so we avoid it.

**Piper licence (resolved 2026-11-14):** `piper-tts` 1.3+ is GPL-3.0-or-later. SeeHere does not import or link it: it is a separate executable, invoked like ffmpeg with a fixed argument list and the text on stdin. A test asserts the `piper` module is never loaded into SeeHere's process. SeeHere's own licence stays the owner's choice. Anyone redistributing a Docker image that contains Piper must also meet GPL-3.0 for that binary (offer its source).
