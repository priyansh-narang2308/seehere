.PHONY: db-up db-down api web test lint typecheck check

db-up:        ## start local Postgres (Docker)
	docker compose -f docker-compose.dev.yml up -d --wait db
db-down:
	docker compose -f docker-compose.dev.yml down
api:          ## run FastAPI with reload on :8000
	cd backend && uv run uvicorn seehere.api.main:app --reload --host 127.0.0.1 --port 8000
web:          ## run Next.js on :3000
	cd web && pnpm dev
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
