.PHONY: db-up db-down migrate api worker web tts-voice test lint typecheck check

db-up:        ## start local Postgres (Docker)
	docker compose -f docker-compose.dev.yml up -d --wait db
db-down:
	docker compose -f docker-compose.dev.yml down
migrate:      ## apply database migrations to DATABASE_URL
	cd backend && uv run alembic upgrade head
api:          ## run FastAPI with reload on :8000
	cd backend && uv run uvicorn seehere.api.main:app --reload --host 127.0.0.1 --port 8000
worker:       ## run the background job worker (Ctrl-C stops after the current job)
	cd backend && uv run python -m seehere.jobs.worker
web:          ## run Next.js on :3000
	cd web && pnpm dev
tts-voice:    ## install Piper as a separate tool (GPL-3.0, never imported) and download the default voice (LJ Speech, public domain) to ~/.cache/seehere/piper
	uv tool install piper-tts
	uv tool run --from piper-tts python -m piper.download_voices en_US-ljspeech-medium --download-dir $(HOME)/.cache/seehere/piper
test:
	cd backend && uv run pytest -q
	cd web && pnpm test
lint:
	cd backend && uv run ruff check src tests && uv run ruff format --check src tests
	cd web && pnpm lint
typecheck:
	cd backend && uv run mypy
	cd web && pnpm typecheck
check: lint typecheck test
