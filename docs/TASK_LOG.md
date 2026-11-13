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
