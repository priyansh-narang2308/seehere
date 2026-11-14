# Task Log

## TASK 01: Repository audit, architecture decisions and runnable foundation
- **Status:** COMPLETE (local). No cloud resources created.
- **Date:** 13 Nov 2026, ~22:40–23:20 IST.

### Reconnaissance
- **Workspace:** `/Users/priyanshnarang/Developer/hackglobal` held only `hackglobal-2026/` (research, strategy, submission, final-strategy and LinkedIn assets). It had no git repo and no code. All prior files were preserved and untouched. The app lives in the new `seehere/` directory with `git init` (branch `main`, **no commits yet**).
- **Tooling found:** Node 26.13, pnpm 11.8, Python 3.12.12 / 3.13, uv 0.8.19, Docker 29.9 (Desktop started during this task), ffmpeg/ffprobe 9.0.2, tesseract 5.5.3, Homebrew Postgres 14 on :5432 (password-protected, not used), gh 2.100. Apple Silicon (arm64), 10 cores, 16 GB.
- **Vultr research:** see `VULTR_RESEARCH_AND_ARCHITECTURE.md`. Key finding: Vultr transcription models advertise only `json`/`text` output, with no word timestamps.
- **Requirements re-check:** see `HACKATHON_REQUIREMENTS.md`. Track 02 confirmed. Deliverables confirmed. Close time and pre-kickoff-code policy are unresolved.

### Implemented
- Backend (`backend/`): FastAPI app factory, env-driven `Settings`, `GET /api/health/live`, and `GET /api/health`. The readiness check covers a real Postgres query, real ffmpeg/ffprobe/tesseract invocations, and AI-key presence (labelled "untested"). It returns 503 when critical components are down and redacts DB credentials. Provider protocols with capability verification states. Ruff, mypy (strict) and pytest are configured.
- Frontend (`web/`): Next.js 16 / React 19 / Tailwind 4. `GET /healthz` (dynamic), and a foundation page that renders live API health in an `aria-live` region. Metadata, background and font set; boilerplate assets removed.
- Dev infra: `docker-compose.dev.yml` (Postgres 16 on 127.0.0.1:5433 with healthcheck), `.env.example`, `.gitignore` (secrets, media, builds), `Makefile` targets.
- Docs: README, ARCHITECTURE, ARCHITECTURE_DECISIONS (9 ADRs), PROJECT_ROADMAP (35 tasks), HACKATHON_REQUIREMENTS, VULTR_RESEARCH_AND_ARCHITECTURE, DEPENDENCIES_AND_LICENSES, TASK_LOG.

### Tests executed and results
| Check | Result |
|---|---|
| `uv run ruff check` / `ruff format` | pass |
| `uv run mypy` (strict, 8 files) | pass, no issues |
| `uv run pytest` | **5 passed**: liveness; missing binary → down; unreachable DB → down with no credential leak; no keys → degraded; readiness shape |
| `pnpm typecheck` (next typegen + tsc) | pass |
| `pnpm lint` (eslint) | pass |
| `pnpm build` | pass (`/` static, `/healthz` dynamic) |
| Live: `curl :8000/api/health/live` | `{"status":"ok"}` |
| Live: `curl :8000/api/health` | overall **degraded**. database ok (postgres 16.15, real query), ffmpeg/ffprobe/tesseract ok, ai_providers degraded (no keys, as expected) |
| Live: `curl :3000/healthz` | `{"status":"ok","service":"web",…}` |
| CORS from :3000 | `access-control-allow-origin: http://localhost:3000` |
| Browser: `http://localhost:3000/` | Status list rendered from the live API |

### Known limitations / blockers
- No AI provider keys yet, so no provider is TESTED.
- Vultr credit is not visible ($0.00). No Vultr resource was created.
- The pre-kickoff code policy is UNKNOWN. This scaffold predates "building starts 14 Nov".
- The `starlette.testclient` deprecation warning (httpx2) is cosmetic.
- No CI workflow yet (added with Task 31/34; local `make check` exists).

## TASK 02: Design system and brand foundation
- **Status:** COMPLETE (local). No cloud resources created. No commits yet.
- **Date:** 13 Nov 2026, ~23:20 IST.

### Implemented
- **Tokens** in `web/src/app/globals.css` (`@theme`): colour, fonts, radius, shadow, animation. Global `:focus-visible` ring. `prefers-reduced-motion` reset. Mirrored in `web/src/lib/tokens.ts` with a WCAG `contrastRatio()` helper.
- **Fonts:** Inter and JetBrains Mono, self-hosted via `next/font`.
- **Primitives** in `web/src/components/ui/`: Button, Badge, VerificationBadge (4 product states), Card family and Eyebrow, Field/Input/Textarea/Checkbox (automatic ARIA wiring), Dialog, Tabs, Toast (`useToast`), Progress, SkipLink, VisuallyHidden, Kbd, Spinner.
- **Brand:** `LogoMark` / `Logo` matching the launch visual.
- **Root layout:** skip link, toast provider, title template `%s · SeeHere`.
- **`/design` page:** a live reference showing contrast ratios computed from tokens, the type scale, and all components in use.
- `cn()` with a tailwind-merge config that knows our custom shadow and radius tokens.
- Vitest + Testing Library + jsdom setup. `make test` now runs backend and web tests.
- `docs/DESIGN_SYSTEM.md`.

### Tests executed and results
| Check | Result |
|---|---|
| `pnpm test` (vitest) | **30 passed**: contrast reference values; every used text pair ≥ 4.5:1; Button (type default, loading/aria-busy, asChild); Field ARIA wiring; Dialog (focus inside, Esc, focus return); Tabs arrow keys; Progress/Badge; axe-core on full showcase with 0 violations |
| `pnpm typecheck` / `pnpm lint` / `pnpm build` | pass (`/`, `/design` static; `/healthz` dynamic) |
| `make check` (backend ruff + mypy strict + pytest, and web lint + typecheck + tests) | pass |
| Browser axe-core on `/design` | **0 violations, 44 passes** (incl. colour contrast); 0 with dialog open |
| Browser keyboard | Skip link visible on first Tab; dialog opens, Esc closes, focus returns to "Open dialog" trigger |
| Browser 375px | no horizontal overflow (`scrollWidth` 375) |

### Fixes made during the task
- `<p>` nested in `<h2>` (invalid). `Eyebrow` now takes `as`.
- Stale dev server not picking up new tokens. Restarted; verified tokens render.
- Removed the `vitest-axe` dependency; tests call `axe-core` directly.
- Removed the temporary in-browser axe file from `web/public`.
- Set `asyncio_default_fixture_loop_scope` to silence a pytest-asyncio config warning.

### Known limitations
- Light theme only; dark theme is not designed yet.
- The axe and keyboard checks cover `/` and `/design`. Product pages (Task 03+) need their own checks.
- jsdom cannot compute colour contrast; contrast is covered by token tests and the browser axe run.
- Not a WCAG conformance claim.
- The `starlette.testclient` → httpx2 deprecation warning remains (cosmetic).

## TASK 03: Application shell and navigation
- **Status:** COMPLETE (local). No cloud resources created. Committed in 8 commits (not pushed).
- **Date:** 14 Nov 2026, 00:02–00:25 IST.

### Implemented
- **Shared layout:** skip link → sticky header → single `<main id="main" tabIndex=-1>` → footer, in the root layout.
- **Header navigation:**
  - Links to Projects and Methodology, plus an "Upload lecture" button. The current section has `aria-current="page"`.
  - Below 640px, a disclosure menu: a button with `aria-expanded`/`aria-controls` that closes on Esc (returning focus to the button) and on navigation.
  - The nav reads the pathname inside `Suspense`, as Next 16 Cache Components requires. Its fallback renders the same links with no current page.
- **Routes:**
  - `/` landing page
  - `/upload`, `/projects`
  - `/projects/[projectId]/processing`, `/projects/[projectId]/results`
  - `/methodology`, `/status` (live API health, moved from home), `/design`
  - 404 and error pages
- **Project routes:**
  - A shared layout with a breadcrumb and section links.
  - The ID must be a UUID. `src/proxy.ts` returns a real 404 for malformed IDs, and the layout's `notFound()` stays as a second check.
  - `params` is read inside `Suspense`, so the pages are partially prerendered.
- **Single source of truth for build status:** `web/src/lib/pipeline.ts` (15 stages, all `not_built`). Home and Methodology show the count from it.
- **New components:** `EmptyState`, `PipelineStageList`, `Container`, `PageHeader`.
- **Honest in-progress pages:** Upload has no file input and says uploads are not open. Projects says storage is not built. Processing and Results say there is no data. Methodology states the system's limits, including that it does not certify WCAG conformance.

### Tests executed and results
| Check | Result |
|---|---|
| `pnpm test` | **53 passed** (+23): active-path matching (7 cases), UUID validation incl. path-traversal strings, aria-current, unknown-path fallback, mobile menu (open, Esc closes and restores focus, closes on route change), one h1 and 0 axe violations on all 8 pages, honesty checks (no file input on Upload, real built-stage count, no WCAG certification claim) |
| `make check` (ruff, mypy strict, pytest 5; eslint, tsc, vitest) | pass |
| `pnpm build` | pass. Static: `/`, `/upload`, `/projects`, `/methodology`, `/status`, `/design`. Partial prerender: project routes. Proxy registered |
| HTTP status, all routes | 200 for valid routes; **404** for `/nope`, `/projects/not-a-uuid/processing`, `/projects/..%2F..%2Fetc/results`, and a UUID with a suffix |
| Browser axe-core, 10 routes × 375/768/1280 px | **0 violations on all 30**; exactly 1 h1 and 1 `<main>` each; **no horizontal overflow** at any width |
| Browser keyboard, 375 px | Tab 1 = skip link; Tab 3 = menu button; Enter opens the menu (current page highlighted); Tab enters the menu; Esc closes it and focus returns to the button |
| Browser keyboard, 1280 px | Tab order: skip → logo → Projects → Methodology → Upload lecture. Skip link focuses `<main>`; the next Tab reaches the breadcrumb. On a project Results page, "Projects" (header) and "Results" (section links) are marked current |
| `/status` live | Correctly showed the database **down** when Docker had stopped; after restarting Docker it showed degraded (DB ok, AI keys untested) |

### Fixes made during the task
- An invalid project ID returned a 200 status (notFound after the streamed shell). Fixed with the proxy.
- The 404 page had a generic tab title. Added "Page not found".
- Removed the design page's own `<main>` and its back link (the layout now owns them).
- Removed the temporary axe file from `web/public` after the browser audit.

### Known limitations
- No project can be reached by clicking yet, because there is no project storage (Task 04) or upload (Task 05). The project routes are reachable by URL only.
- The status code for a well-formed UUID of a project that doesn't exist will need the same proxy-or-API approach once projects exist (Task 04/05).
- Screen-reader testing (VoiceOver/NVDA) is planned for Task 32. This task used axe and keyboard only.
- The pipeline stage list will change as later tasks land. Only those tasks may flip a stage to `built`.

## TASK 04: Database schema and migrations
- **Status:** COMPLETE (local). No cloud resources created. Committed in 4 commits (not pushed).
- **Date:** 14 Nov 2026, 00:10–00:18 IST.

### Implemented
- **Base:** `backend/src/seehere/db/base.py`.
  - A declarative `Base` with a deterministic constraint-naming convention, so migrations are stable.
  - UUID primary-key, `created_at` and `updated_at` mixins.
  - `str_enum()`: enums are stored as text with a CHECK constraint, not as native Postgres enums, so adding a value is a simple migration.
- **Domain enums:** `db/enums.py`. Project, job, visual, reference, description, verification, review, evidence, solver, schedule and export states.
  - The verification states match the product: `verified_text_match`, `corroborated`, `uncertain`, `needs_review`.
- **18 tables:** `db/models/`.
  - The tables: project, media_asset, job, transcript_segment, transcript_word, frame, slide, ocr_region, visual_unit, reference_link, description_cue, evidence, verification_event, schedule_run, schedule_placement, audio_clip, review_decision, export_artifact.
  - Rules are enforced by the database, not only by Python:
    - Normalized bounding boxes (0–1, positive size) and start < end time ordering.
    - A SHA-256 hex check on media files; job progress between 0 and 1; a unique job idempotency key.
    - Every evidence row points to the source its kind requires.
    - A "linked" reference must have a target region or unit.
    - A schedule pause must give a reason; an "edit" review must carry the edited text.
  - Every foreign key is indexed. Deleting a project cascades through its lineage.
  - A partial index `ix_job_claimable` is ready for the Task 06 worker.
- **Session:** `db/session.py`. A cached engine and session factory, plus a `get_db()` FastAPI dependency.
- **Alembic:** `backend/migrations`.
  - It reads the URL from settings, so no credentials are in `alembic.ini`, and compares column types.
  - The initial migration creates 18 tables and 31 indexes. Run it with `make migrate`.

### Tests executed and results
| Check | Result |
|---|---|
| `test_migrations.py` (4) | upgrade creates exactly the model tables; **no drift** between models and migration (`compare_metadata` empty); every FK column indexed; downgrade to base drops everything, then upgrade again succeeds |
| `test_models.py` (12) | Defaults; DB-level cascade delete; enum CHECK rejects unknown values; status/progress/hash/box/time/evidence/reference/pause/review rules each rejected by Postgres; a full lineage through every table inserts and cascades |
| Test isolation | A throwaway `seehere_test` database is dropped and re-created (the name must end in `_test`). Each test runs in a savepoint that is rolled back |
| `make check` | pass (ruff, mypy strict) |

### Fixes made during the task
- Evidence source FKs and reference word FKs had no index. Added indexes and regenerated the migration (caught by the FK-index test).
- `now()` is fixed within one transaction, so the ordering test sets `created_at` explicitly.

### Known limitations
- The schema follows the planned pipeline. Later tasks may add columns through new migrations, never by editing this one.
- No row-level multi-tenancy: there are no user accounts in this build.

## TASK 05: Secure upload system
- **Status:** COMPLETE (local). No cloud resources created. Committed in 11 commits (not pushed).
- **Date:** 14 Nov 2026, 00:19–00:35 IST.

### Implemented
- **Upload API:** `POST /api/projects`, in `backend/src/seehere/api/projects.py`.
  - The request body is the raw file, streamed to disk in 1 MiB chunks, so the whole file is never held in memory.
  - Metadata travels in URL-encoded headers: `X-SeeHere-Title`, `X-SeeHere-Filename` and `X-SeeHere-Rights-Confirmed`.
  - Checks, in order:
    1. The rights confirmation is required (400).
    2. The title must be 1–200 characters.
    3. The filename is sanitized: the path is stripped, it is Unicode-normalized, unsafe characters are replaced, and its length is capped.
    4. The size cap is enforced from Content-Length (413), and again while streaming (413). An empty body is rejected (400).
    5. **ffprobe identifies the content.** The extension and Content-Type are ignored.
  - The ffprobe call uses `-protocol_whitelist file -format_whitelist mov,matroska`, so HLS playlists, concat lists, images and text are refused (415).
  - The file needs a real video stream (not cover art) and an audio stream (422 `no_audio_stream`), and a duration within the limit (422 `too_long`).
- **Storage:** `media/storage.py`.
  - Files are written to temp with mode 0600, then atomically moved to a server-chosen path: `{project_uuid}/source.{ext}`.
  - `MediaStore.resolve` blocks path escapes, including through symlinks.
  - If the database commit fails, the stored file is removed.
  - The project gets `expires_at = now + retention_hours`.
- **Read endpoints:**
  - `GET /api/projects` (newest first, up to 100) and `GET /api/projects/{id}` (404 `not_found`).
  - `GET /api/config/upload` returns the size and duration limits, accepted formats and the retention period.
  - Responses never expose the storage path or file hash. All errors use one shape: `{"error":{"code","message"}}`.
- **Web: Upload page** (`/upload`).
  - A real form: a file input (with an accept list taken from the server), a title that auto-fills from the filename, and a rights checkbox.
  - Client checks mirror the server's, and focus moves to the first invalid field.
  - Shows byte-level progress (XHR) and a cancel button, then a "Checking the video…" state. Server refusal reasons appear in an alert. Success leads to the project's Processing page.
- **Web: Projects page** (`/projects`). A live list showing the title, upload date, length, size, format and status, with loading, error (with retry) and empty states.
- **Web: Processing page.** An "Upload checked" panel with the server-measured file facts (name, length, resolution, size, format, codecs) and the expiry time. It says plainly that analysis has not started.
- **Web: project routes.** They load the real project. The breadcrumb shows its title. `src/proxy.ts` asks the API and returns a **real 404** for unknown projects. If the API is down, the error page shows instead of a false 404.
- `pipeline.ts`: the "Upload and rights check" stage is now `built`. That is 1 of 15 stages.

### Tests executed and results
| Check | Result |
|---|---|
| Backend `pytest` | **66 passed** (+45 this task: 20 storage, 25 upload). Real ffmpeg-generated MP4, MOV, WebM and MKV files are each accepted and stored with the right type and codecs |
| Upload rejects (all tested) | Missing or non-`true` rights; empty, blank or over-long title; oversized by header and by stream; empty body; plain text, HLS playlist, concat list and PNG all named `.mp4` (415); video with no audio, audio-only MP4, and over the duration limit (422). A failed database write leaves no file. No file is left in temp or media after any reject |
| Path safety | Filenames with `../`, Windows `..\` paths, absolute paths, control characters, NUL bytes and reserved characters are sanitized; non-English names are kept; long names are capped by UTF-8 bytes. The stored path never uses the filename. `resolve()` refuses `..`, absolute paths, NUL and symlink escapes. Temp and stored files are mode 0600 |
| Web `pnpm test` | **97 passed** (+44): API client (format helpers, error mapping, XHR upload with a fake XHR: headers, progress, phases, abort, network error), form validation and flow (errors, focus order, progress bar, navigation on success, server refusal shown, works without limits), project list states and axe, SourceFacts, proxy (malformed, unknown, existing, API down) |
| `make check` | pass (ruff, mypy strict, pytest, eslint, tsc, vitest) |
| `pnpm build` | pass. Project routes are partially prerendered |
| Browser: real upload | 8 s 640×360 H.264/AAC test video through the real form → "Uploading 0 B of 122 KB" → "Checking the video…" → Processing page showing the measured facts. The project appears in `/projects` |
| Browser: refusal | An HLS playlist named `.mp4` → "This file is not a supported video…", with the form still usable |
| Browser: axe-core (WCAG 2.1 A/AA + best practice) | **0 violations** on `/upload` (with an error showing), `/projects` (with items) and a project's Processing page |
| HTTP status | Unknown UUID **404**; malformed ID **404**; existing project 200 |
| API down | Projects shows "could not be reached" with Try again; the project page shows the error boundary, not a 404 |

### Fixes made during the task
- `.gitignore` had `media/`, which also ignored the `seehere/media` source package. Anchored it to `/media/`.
- The upload page claimed files "are deleted automatically". There is no deletion job yet, so it now states the real retention period and that automatic deletion is not built.
- From the browser test:
  - Focus went to the title even though the file field comes first. Fixed.
  - A stale title error stayed after the title auto-filled. Fixed.
  - "10:00 long" was ambiguous; it now reads "10 minutes".
  - The success toast said "ready for processing"; it now says "uploaded and checked".
  - A well-formed but unknown project ID returned a 200 status. Fixed in the proxy.

### Known limitations
- **Expired uploads are not deleted yet.** `expires_at` is recorded, but the cleanup job needs the worker from Task 06.
- No authentication or user accounts: anyone who can reach the API can upload and list. This is acceptable only for a local or demo deployment. The project list is not per-user.
- No upload resume. A dropped connection means starting again. Uploads go straight to the API, not to object storage.
- ffprobe identifies the container and streams; it does not prove the video plays end to end. Full decode and normalization come in Task 07.
- The `starlette.testclient` deprecation warning remains (cosmetic).

## TASK 06: Background jobs and orchestration
- **Status:** COMPLETE (local). No cloud resources created. Tasks 06 and 07 were committed together in 10 code commits plus 1 docs commit (not pushed).
- **Date:** 14 Nov 2026, 00:36–00:56 IST.

### Implemented
- **Queue (`seehere/jobs/queue.py`, ADR-005).** Built on the existing `job` table.
  - `enqueue` is idempotent (`ON CONFLICT (idempotency_key) DO NOTHING`) and doesn't commit, so a job is committed together with the data it refers to.
  - `claim` does `UPDATE … WHERE id = (SELECT … FOR UPDATE SKIP LOCKED LIMIT 1)`, so two workers never get the same job. It only takes jobs whose `run_after` has passed and whose kind the worker can handle.
  - **Leases:** every update after a claim is guarded by `locked_by = <worker>`. A worker that lost its job can never overwrite newer state. All times come from the database clock.
  - **Retries:** unexpected errors are retried with exponential backoff (10 s, 20 s, 40 s… capped at 300 s) until `max_attempts` (default 3). `PermanentJobError` fails at once.
  - **Cancellation:** a queued job is cancelled at once. A running job gets `cancel_requested`; the worker sees it on its next heartbeat or progress report and stops, killing ffmpeg if it's running.
  - **Retry after failure or cancel:** resets attempts and starts a fresh run.
  - **Crash recovery:** `recover_stale` re-queues running jobs whose heartbeat is older than `job_stale_after_s` (60 s). A job out of attempts fails instead, and a job with a pending cancel is cancelled.
  - **Project status is derived from its jobs:** processing while any job is active, failed if one failed, otherwise uploaded. "Ready" stays unreachable until the full pipeline exists.
- **Worker (`seehere/jobs/worker.py`, `make worker`).**
  - Claims and runs jobs. A heartbeat thread refreshes the lease every 5 s and watches for cancel requests.
  - `JobContext.progress(stage, fraction)` stores throttled progress.
  - Errors are recorded with a **user-safe message**. Unexpected errors show only "An unexpected error stopped this step."; the full traceback goes to the worker log only.
  - Maintenance (stale recovery and retention) runs every 60 s on every worker.
  - SIGINT/SIGTERM stop the worker after the current job. A hard kill is recovered through the lease.
- **Retention (`seehere/jobs/retention.py`).** Delivers the 24 h deletion that Task 05 openly said was missing.
  - Expired projects are locked with SKIP LOCKED; their media directory is removed and their rows deleted (cascading to every derived row).
  - Projects with a running job wait until it ends.
  - Abandoned partial uploads and work directories in `media/tmp` older than 6 h are removed too.
  - `remove_tree` refuses symlinks and paths outside the media root.
- **Upload integration.** Each upload now enqueues `media.prepare` **in the same transaction** as the project and media rows, so a project can't exist without its first job.
- **API (`seehere/api/jobs.py`).**
  - `GET /api/projects/{id}/jobs` returns the jobs plus the server's clock.
  - `POST /api/jobs/{id}/cancel` and `POST /api/jobs/{id}/retry`:
    - Both return 409 when the job is in the wrong state.
    - Both **require the `X-SeeHere-Request: 1` header**, so another site can't trigger them: the custom header forces a CORS preflight that only the app's origin passes.

### Tests executed and results
| Check | Result |
|---|---|
| `test_jobs.py` (23) | Idempotent enqueue. Claim filters (kind, `run_after`). **SKIP LOCKED skips a row another transaction holds** (deterministic). **8 threads racing for 40 jobs: every job claimed exactly once.** Only the lease holder can heartbeat, report progress, complete or cancel. Backoff values and cap. Retryable vs permanent failures. Queued vs running cancel. Retry rules. Stale recovery (re-queue, fail when out of attempts, cancel). Project status derivation. Worker: progress, retry with a safe message (a fake secret path never reaches the job row), permanent failure, live cancel of a running job, lost lease never overwrites, clean loop stop. **A real worker process is SIGKILLed mid-job: the job stays running until the heartbeat goes stale, is re-queued, and a new worker finishes it (attempt 2)** |
| `test_retention.py` (5) | Only expired projects are deleted (files, rows and cascaded jobs); a running job defers deletion; idempotent when files are already gone; only old temp entries are removed; symlink and `..` escapes are refused, and files outside the media root are kept |
| `test_jobs_api.py` (7) | Upload queues the job; worker outputs served; empty outputs before preparation; cancel/retry need the header (403) and the right state (409); unknown IDs give 404; a frame row pointing outside media gives 404, never the file; a cross-site preflight from another origin gets no CORS approval |
| Live (dev stack, `make worker`) | Upload → Waiting → Running → Done on the Processing page. **Cancel in the UI:** Running → Stopping… → Cancelled, with only `source.mp4` left on disk and `tmp/` empty. **Run again:** Waiting → Running → Done. **Retention:** an expired project was deleted by the worker's sweep within 30 s (files gone, API 404, web 404) |

### Known limitations
- Delivery is at-least-once. Handlers must be idempotent; the one handler so far is, and that is tested.
- No jitter in the backoff. With single-digit workers this is fine.
- No worker registry. The UI infers "the worker may not be running" from a job waiting more than 15 s.
- SIGTERM waits for the current job. If a container stop kills the worker before that, the job is recovered after 60 s.
- Projects uploaded before this task have no job. Their Processing page says no analysis was queued.

## TASK 07: Media inspection and normalization
- **Status:** COMPLETE (local). No cloud resources created.
- **Date:** 14 Nov 2026, 00:44–00:56 IST.

### Implemented
- **Safe ffmpeg runner (`seehere/media/ffmpeg.py`).**
  - A fixed argv list, never a shell. `-nostdin`.
  - Inputs are opened with `-protocol_whitelist file`, the `mov,matroska` demuxers only, and a `file:` path prefix, so a file can't make ffmpeg open a URL, a playlist or another file.
  - Live progress comes from `-progress pipe:1`.
  - There is a timeout (900 s), and the process is **killed on cancel or timeout**.
  - stderr goes to a temp file, so it can't block. Its tail is logged, never shown to users.
- **`media.prepare` handler (`seehere/media/normalize.py`).**
  1. Re-inspects the stored file with the upload's content rules; corrupt input fails permanently with a user-safe message.
  2. Extracts the first audio track as **16 kHz mono 16-bit PCM WAV** and verifies the result with ffprobe (wav demuxer only): codec, rate, channels and duration.
  3. Samples **1 frame per second** (configurable), scaled to at most 1280 px wide, as JPEGs.
     - Frame *n* is **the picture on screen at *n*/fps**: ffmpeg's `fps=…:round=up` takes the last frame at or before that time, and the file is named by *n* (`-frame_pts`).
  4. All work happens in a private temp directory. Outputs are moved into place, and the old outputs are replaced, in one transaction. Re-running leaves exactly one set.
  - Progress stages are inspect → audio → frames → save.
- **Outputs API.**
  - `GET /api/projects/{id}/media`: audio facts, frame count, rate and range, and up to 48 evenly spaced preview frames.
  - `GET /api/frames/{id}/image`: the JPEG, resolved through `MediaStore`, with `nosniff`, a private cache and `inline`.
- **Web: Processing page.** A live **Analysis** panel.
  - It polls once a second while work is active and stops when idle.
  - It shows the stage with a progress bar, the attempt count, retry timing, failure reasons, and Cancel / Try again / Run again buttons.
  - It hints when no worker seems to be running.
  - When finished it shows the audio and frame summary and a frame preview grid with alt text ("Video frame at 0:16").
  - A screen-reader live region announces status changes only, not every progress tick.
  - When work finishes, the server-rendered status badge is refreshed.
- `pipeline.ts`: the "Media inspection" stage is now **built** (2 of 15).
- **Copy changes:**
  - Upload page: "The video and everything made from it are deleted 24 hours after upload."
  - Source facts: "Scheduled for deletion on …".

### Tests executed and results
| Check | Result |
|---|---|
| `test_media_prepare.py` (15) | **Frame timing proven by content:** an 8 s video whose brightness rises with time; each sampled frame is compared with a reference frame decoded independently at the stored time (±6 of 255). WAV is pcm_s16le, 16 kHz, mono, 8.0 s, about 32,000 bytes per second, mode 0600. fps=2 and max-width limits applied (16 frames at 0.5 s steps, 320×180). Re-run replaces outputs (1 audio, 8 frames, 10 files). HLS playlist, header-only MP4 and truncated MP4 fail permanently with no outputs and a clean temp dir. Missing source file fails. Cancel mid-frames leaves no outputs. Runner: progress reaches 1.0 in order; cancel kills ffmpeg in under 5 s; timeout; failure detail kept for logs; an HLS playlist input can't reach the network |
| Backend total | **116 passed** (+50) |
| Web `pnpm test` | **105 passed** (+8 JobPanel: running stage and progress, polling until done then outputs, frame alt text and URLs, refresh, polling stops when idle, axe 0 violations; failure + Try again with the header; Cancel → Run again; scheduled retry text; worker-down hint; API down; no actions while stopping) |
| `make check` | pass (ruff, mypy strict, pytest, eslint, tsc, vitest); `pnpm build` passes |
| Live, browser | A 90 s 1280×720 upload → **90 frames at 1/s (0:00–1:29), 16 kHz mono 1:30 (2.7 MB)**. All 12 preview images loaded at 1280×720. **axe-core: 0 violations** on the Processing page with results |

### Fixes made during the task
- **Frame timing bug found by the reference test.** With ffmpeg's default `fps` rounding, frame *n* actually showed time *n* + 0.4 s: it is the last frame in [*n* − 0.5, *n* + 0.5). Fixed with `round=up`, then re-checked against the decoded ground truth. Every frame now matches.
- **JobPanel render loop.** Polling depended on the router object; with an unstable one it re-fetched thousands of times. The router is now read through a ref, and a test asserts that polling stops.

### Known limitations
- Frames are sampled at a fixed rate. Scene and slide-change keyframes are Task 09.
- Only the first audio track is used. A lecture with the speech on another track would need a choice in the UI.
- ffprobe and ffmpeg confirm the streams decode. They don't judge audio quality: silence or music-only audio passes this stage and will show up in speech-to-text (Task 08).
- Frame images are served by the API without authentication, like everything else in this build (no accounts yet). Paths can't be guessed (UUIDs), but this is only fit for local or demo use.

## Task 08: Speech-to-text (2026-11-14) ✅

### Implemented
- **Local STT** (`providers/stt_faster_whisper.py`): faster-whisper `small.en`, int8 on CPU, word timestamps, VAD filter, `condition_on_previous_text=False`. Words are kept in time order and inside the audio; confidence is clamped to 0–1. The 16 kHz WAV is read directly (PyAV is not used: its current release breaks faster-whisper's decoder, and this keeps a second media decoder off user-derived files). The model is cached once per process. **TRANSCRIBE_TEXT and TRANSCRIBE_WORD_TIMESTAMPS: TESTED.**
- **Vultr STT** (`providers/stt_vultr.py`): text only, OpenAI-style multipart request. **DOCUMENTED, not TESTED**: no live call made (it spends credit). The request shape is an assumption until an approved live test (`SEEHERE_LIVE_VULTR_STT=1`). Not used by the pipeline.
- **Job `speech.transcribe`**, queued in the same transaction as media preparation's outputs. One job row per project (`enqueue_or_restart`): new audio re-queues it, and the old transcript is deleted with the old audio (FK cascade). Writes `transcript_segment` / `transcript_word` rows; metadata in the audio asset's `probe.transcript`. Model load failures are retried with a user-safe message (new `RetryableJobError`).
- **API** `GET /api/projects/{id}/transcript`. **Web:** speech stage labels, a transcript list on the Processing page, stage 03 marked built (3 of 15).

### Tests
| Check | Result |
|---|---|
| Real speech (`tests/speech_clip.py`) | Two sentences from system TTS (macOS `say` / `espeak-ng`) joined by exactly 2.0 s of silence; the pause is located in the signal by energy as the independent reference |
| `test_stt_faster_whisper.py` (8) | Expected words recognized; timings ordered and inside the audio; **"left" ends and "Sales" starts at the measured silence (±0.4 s)**, no word inside it; progress and stop; TESTED flags; English-only; WAV format refused; unloadable model reported |
| `test_transcribe.py` (6), `test_transcript_api.py` (2) | Upload → prep → transcript rows in DB and over HTTP; re-run replaces; new audio re-queues the same job; missing audio fails permanently; model failure retried with message; cancel mid-recognition leaves no rows |
| `test_stt_vultr.py` (5 + 1 skipped live) | Fake transport only: request shape, key never in errors, 25 MB limit, DOCUMENTED flags |
| Backend / Web | **139 passed, 1 skipped** / **107 passed** |
| Live | 8 s speech video uploaded → both jobs done in ~6 s → 16 words, 2 segments, transcript shown on the page |

### Known limitations
- `small.en` is English only. Other languages need a multilingual model (setting `LOCAL_STT_MODEL`).
- Cancellation is checked between recognizer segments (about every 30 s of audio).
- Whisper can mis-hear technical terms and occasionally invent text in music or noise; VAD reduces but does not remove this. The UI says machine transcription can contain errors.
- The first run downloads the model (about 480 MB) from Hugging Face.

## Task 09: Scene and slide change detection (2026-11-14) ✅

### Implemented
- **`media/scenes.py`**, job `scenes.detect`, queued with speech-to-text after media preparation (one row per project).
  - Each sampled frame → 64×36 grayscale thumbnail (Pillow, JPEG draft decode).
  - A frame is a keyframe when ≥ `scene_change_fraction` (2%) of thumbnail pixels differ by > `scene_pixel_delta` (24/255) from the **last keyframe** (catches slow drift) **and** the next frame is nearly the same (a transition yields one keyframe on the settled slide).
  - **Dedupe:** a settled picture matching an earlier scene reuses its `scene_index` and is not a new keyframe.
  - Every frame gets `scene_index` and a 64-bit dHash in `phash`. Re-runs rewrite all three fields (idempotent).
- **API:** `GET /api/projects/{id}/media` now has `scenes: {keyframes, revisits}` (null until detection has run).
- **Web:** keyframe grid ("Keyframe at 0:18"), scene and revisit count, stage 04 marked built (4 of 15).

### Tests
| Check | Result |
|---|---|
| Demo clip (`test_scenes.py`) | 34 s synthetic lecture with noise + H.264: a cut, a bullet build (~3% of the picture), a 2 s crossfade, a revisited slide. **Keyframes exactly 0, 6, 12, 18, 28 s; revisit at 24 s deduplicated; precision 1.0 and recall 1.0**; every frame in the right scene; the half-faded frame stays with the old slide |
| Unit | Noise alone gives no change; gradual drift caught against the last keyframe; mid-transition frame skipped; dHash; re-run identical |
| Backend / Web | **146 passed, 1 skipped** / **108 passed** |
| Live | Demo clip uploaded → 3 jobs done; page shows "5 scenes … plus 1 return to an earlier slide" and the 5 keyframes |

### Known limitations
- Thresholds are tuned on synthetic slides. A talking-head video with camera motion, or a moving pointer or laser dot, can produce extra keyframes; real-lecture precision is not measured yet.
- Changes are found at the sampling rate (1 per second); a slide shown for less than about 2 s may be missed.
- A uniform brightness change (camera exposure) counts as a change.

## Task 10: OCR and text evidence (2026-11-14) ✅

### Implemented
- **`media/ocr.py`**, job `ocr.extract`, queued by scene detection (keyframes only, so a revisited slide is read once).
  - Each keyframe: grayscale, 2× upscale below 1600 px wide, then `tesseract <png> stdout -l eng --psm 3 tsv` (argv only, timeout, `OMP_THREAD_LIMIT=1`).
  - TSV words grouped into lines; each line becomes an `ocr_region` with its text **as read**, mean confidence 0–1, and a box as fractions of the frame. Lines below `ocr_min_confidence` (0.3) or with no letters or digits are dropped.
  - Re-runs replace all regions. A missing or failing Tesseract is retried with "Text recognition failed on a keyframe."
- **`text/numbers.py`** for later seen-versus-said and claim checks:
  - `extract_numbers`: thousands separators, decimals, Unicode minus, %, $ € £ ¥ ₹, k/M/bn/million; ignores digits inside words and version strings.
  - `words_to_number` ("three hundred and twelve" → 312, "four point two five" → 4.25).
  - `fix_ocr_digits` ("1O0" → 100, "Oslo" untouched).
  - `same_number`: allows for the rounding a slide shows ("$3.2M" ≈ 3,180,000; "12.5%" ≈ 0.125).
- **API:** `GET /api/projects/{id}/ocr`. Job lists now break `created_at` ties by pipeline order.
- **Web:** an "On-screen text" list by keyframe, low-confidence lines marked, an "evidence, not verified fact" note; stage 05 marked built (5 of 15).

### Tests
| Check | Result |
|---|---|
| `test_ocr.py` (7) | Slides drawn with known text: **every line read exactly** at 1280 and 640 px; **box IoU > 0.6** against the drawn box; confidence > 0.6; numbers parsed as 12.5, 3,200,000, 41.7, 2022. Blank slide gives no text. TSV grouping and filtering. Missing binary and bad language reported. End to end: 2 keyframes read, the revisit skipped, re-run identical; missing Tesseract retried with a message |
| `test_numbers.py` (35) | All the forms above, plus rejections |
| Backend / Web | **188 passed, 1 skipped** / **109 passed** |
| Live | Deck video → 4 jobs done; page shows both slides' text (confidence 0.94–0.97) |

### Known limitations
- Tested on clean rendered slides. Handwriting, photos of whiteboards, low-contrast or stylized text, and equations will read worse; real-lecture accuracy is not measured yet.
- English only (`eng`); other languages need their Tesseract data and `OCR_LANGUAGE`.
- No table or chart structure: each line is plain text. Chart values come from visual analysis (Task 12).

