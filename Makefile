.PHONY: dev dev-backend dev-frontend test lint typecheck e2e build clean migrate load-test docs help tf-plan tf-apply k8s-deploy

# ─── Default ──────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  QuantNexus — Available Commands"
	@echo "  ──────────────────────────────────────────────"
	@echo "  make dev           Start full local dev stack (Docker)"
	@echo "  make dev-backend   Start only the FastAPI backend (uv)"
	@echo "  make dev-frontend  Start only the Next.js frontend (npm)"
	@echo "  make test          Run all tests (backend + frontend)"
	@echo "  make lint          Run all linters (ruff + eslint)"
	@echo "  make typecheck     Run mypy (backend) + tsc (frontend)"
	@echo "  make e2e           Run Playwright E2E tests"
	@echo "  make load-test     Run k6 WebSocket load test (ws_market.js)"
	@echo "  make docs          Open project documentation"
	@echo "  make build         Build production Docker images"
	@echo "  make migrate       Run database migrations (alembic)"
	@echo "  make clean         Remove build artifacts and caches"
	@echo ""

# ─── Development ──────────────────────────────────────────────────────────────
dev:
	docker compose up --build

dev-backend:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev

# ─── Load Testing ─────────────────────────────────────────────────────────────
load-test:
	@echo "Running k6 WebSocket load test..."
	k6 run tests/load/ws_market.js

# ─── Testing ──────────────────────────────────────────────────────────────────
test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest tests/ -v

test-frontend:
	cd frontend && npm run test

test-e2e:
	cd frontend && npm run test:e2e

# ─── Typecheck ────────────────────────────────────────────────────────────────
typecheck:
	cd backend && uv run mypy app/
	cd frontend && npx tsc --noEmit

# ─── E2E ──────────────────────────────────────────────────────────────────────
e2e:
	cd frontend && npx playwright test tests/e2e/ --reporter=list

# ─── Docs ─────────────────────────────────────────────────────────────────────
docs:
	@echo "Open docs/architecture/system-overview.md to get started"

# ─── Linting ──────────────────────────────────────────────────────────────────
lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check app/ tests/
	cd backend && uv run ruff format --check app/ tests/

lint-frontend:
	cd frontend && npm run lint
	cd frontend && npx tsc --noEmit

# ─── Database ─────────────────────────────────────────────────────────────────
migrate:
	cd backend && uv run alembic upgrade head

migrate-down:
	cd backend && uv run alembic downgrade -1

migrate-generate:
	cd backend && uv run alembic revision --autogenerate -m "$(MSG)"

# ─── Build ────────────────────────────────────────────────────────────────────
build:
	docker compose build

# ─── Clean ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf frontend/.next frontend/out
	rm -f backend/test.db test.db
	@echo "Clean complete."

# ─── Infrastructure ───────────────────────────────────────────────────────────
tf-plan:
	cd infra/terraform && terraform plan

tf-apply:
	cd infra/terraform && terraform apply

k8s-deploy:
	kubectl apply -f infra/k8s/
