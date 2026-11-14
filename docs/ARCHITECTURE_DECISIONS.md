# Architecture Decision Records

Format: Context → Options → Decision → Consequences. Status: Accepted unless noted. Date: 13 Nov 2026.

## ADR-001: Single modular app + one worker on one Vultr Compute VM
- **Context:** a ~36 h build, mandatory Vultr Compute backend, one demo workload (2–3 min clips).
- **Options:** (a) microservices on Kubernetes/Clusters; (b) one VM with Docker Compose (Caddy, web, API, worker, Postgres); (c) frontend on a separate host.
- **Decision:** (b). Clusters, Instance Templates and Kubernetes are rejected (see `VULTR_RESEARCH_AND_ARCHITECTURE.md` §4). The frontend is served from the same VM, so there is no Vercel dependency.
- **Consequences:** a single point of failure, accepted for a demo and mitigated by a snapshot plus a pre-processed sample. Vertical resize is the scaling path.

## ADR-002: Backend in Python 3.12 + FastAPI + Pydantic v2
- **Context:** the pipeline needs FFmpeg, OCR, OR-Tools, faster-whisper, pypdf and PPTX parsing, all Python-first.
- **Options:** Node/TS backend; Python FastAPI; Django.
- **Decision:** FastAPI, with typed Pydantic models and an OpenAPI schema at `/api/docs`.
- **Why 3.12 and not the host's 3.13:** CTranslate2 (faster-whisper) and OR-Tools wheels are most reliable on 3.12. Managed by **uv** with a lockfile.
- **Consequences:** two languages in the repo, separated by an explicit HTTP contract.

## ADR-003: Frontend in Next.js 16 (App Router) + TypeScript + Tailwind CSS 4
- **Context:** a premium, accessible SaaS UI with a video player, timelines and an evidence inspector.
- **Options:** Next.js; Vite + React SPA; SvelteKit.
- **Decision:** Next.js 16 (current create-next-app output), TypeScript strict, Tailwind 4, React 19. Accessible primitives (dialogs, menus, tabs) come from **Radix UI** in Task 02, chosen for WAI-ARIA-conformant behaviour and an unstyled API that fits our design tokens.
- **Note:** Next 16 enables `cacheComponents`. Data-fetching pages must use Suspense/`connection()` correctly. The bundled docs in `node_modules/next/dist/docs` are authoritative.
- **Consequences:** `pnpm typecheck` runs `next typegen` first, because `LayoutProps` types are generated.

## ADR-004: PostgreSQL 16 + SQLAlchemy 2 + Alembic
- **Context:** a relational, provenance-heavy model (evidence ledger) with foreign keys and indexes.
- **Decision:** Postgres 16 in Docker (dev on port 5433; prod in Compose). SQLAlchemy 2 typed ORM, psycopg 3 driver, Alembic migrations (Task 04). Managed Postgres is rejected on cost/need.

## ADR-005: Job queue on Postgres (`FOR UPDATE SKIP LOCKED`), not Redis
- **Options:** Redis + RQ/ARQ/Dramatiq/Celery; Postgres-backed queue.
- **Decision:** Postgres-backed `job` table claimed with `SELECT … FOR UPDATE SKIP LOCKED`, with heartbeat, attempts, cancellation flag and idempotency key (Task 06).
- **Why:** job state must be durable and queryable alongside results for progress UI and audit anyway. It removes a service, and throughput needs are tiny (single-digit concurrent jobs).
- **Consequences:** we own ~150 lines of queue code, which need tests for double-claim and crash recovery.

## ADR-006: Provider adapters with tested-capability tracking
- **Decision:** `seehere.providers.base` defines `SpeechToText`, `VisionAnalyzer`, `TextGenerator` and `TextToSpeech` protocols. Each adapter publishes capabilities as `DOCUMENTED`, `TESTED` or `UNAVAILABLE`, and the pipeline may only depend on `TESTED`. A mocked adapter never counts as a passed integration test.
- **Initial assignment (to be confirmed by tests):**
  - **STT with word timestamps:** local **faster-whisper** on the VM. Vultr's transcription models advertise only `json`/`text` output (no word timings), so they can't drive speech-safe scheduling.
  - **Vision (structured JSON):** Vultr Serverless Inference `qwen3.8-flash-next` (image input + `structured_outputs` per catalog). Gemini is the alternative.
  - **TTS:** Vultr Serverless Inference `qwen3-tts-12hz-1.7b`; local Piper as the no-network fallback.
  - **Text generation:** the same Vultr chat model as vision.

## ADR-007: Scheduling = greedy baseline + OR-Tools CP-SAT, measured
- **Decision:** implement both on identical inputs (Tasks 19–20). CP-SAT is kept only if the benchmark shows a measurable gain (coverage of priority units at zero speech overlap, or less added duration). Otherwise we simplify and report that honestly.

## ADR-008: Deployment via Docker Compose + Caddy (automatic HTTPS)
- **Decision:** Caddy terminates TLS (Let's Encrypt), routes `/api/*` to FastAPI and everything else to Next.js. Only 22 (restricted), 80 and 443 are open. A non-root deploy user, SSH keys, a Vultr Firewall Group, and Cloud-Init only for installing Docker and creating the user.

## ADR-009: Local media volume with 24 h retention (no Object Storage yet)
- Revisit if measured storage growth exceeds about 50% of disk.
