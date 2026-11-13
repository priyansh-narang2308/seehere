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
