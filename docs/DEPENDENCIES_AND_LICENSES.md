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
OR-Tools (Apache-2.0) · faster-whisper (MIT) + Whisper model weights (MIT) · PySceneDetect (BSD-3) · OpenCV (Apache-2.0) · PyMuPDF (**AGPL-3.0**: acceptable for a public open-source repo; otherwise use pypdf) · python-pptx (MIT) · Piper TTS (MIT; voice licences per voice).

## Baseline (not part of our product)
microsoft/ai-audio-descriptions (MIT) is run unmodified as a comparison baseline in Task 29, with attribution. Its code is not copied into SeeHere.

## Hosted models (Vultr Serverless Inference, used via API)
Model licences are per the Vultr catalog and model cards. `auk` is "evaluation only", so we avoid it.
