# Makefile
.PHONY: setup dev build test lint fmt typecheck start check ci

# Defaults for scraper targets (can be overridden per-invocation)
SCRAPER_CONCURRENCY ?= 1
QUEUES ?= scrape.job,scrape.post

setup:         ## install toolchains + deps
	asdf install || true
	[ -f package.json ] && npm ci || true
	[ -f pyproject.toml ] && python -m pip install -U pip && pip install -e . || true
	pre-commit install || true

dev:           ## run dev servers
	[ -f package.json ] && npm run dev || true

build:
	[ -f package.json ] && npm run build || true

test:
	[ -f package.json ] && npm test --silent || true
	[ -f pytest.ini -o -f pyproject.toml -o -f requirements.txt -o -d tests ] && pytest -q || true

test.live:
	# Run tests with real Google Sheets data
	@echo "Running live tests with real data..."
	LIVE_TESTS=1 pytest tests/live -v -s

test.components:
	# Run component tests (may use real data if credentials available)
	pytest tests/components -v

test.unit:
	# Run only unit tests (no external dependencies)
	pytest tests/unit -v

test.integration:
	# Run integration tests
	pytest tests/integration -v

test.smoke:
	# Quick smoke test to verify setup
	@echo "Running smoke test to verify configuration..."
	python test_smoke.py

lint:
	[ -f package.json ] && npm run lint || true
	command -v ruff >/dev/null 2>&1 && ruff check . || true

fmt:
	[ -f package.json ] && npm run fmt || true
	command -v ruff >/dev/null 2>&1 && ruff format . || true
	command -v black >/dev/null 2>&1 && black . || true

typecheck:
	[ -f package.json ] && npm run typecheck || true
	command -v mypy >/dev/null 2>&1 && mypy . || true
	command -v pyright >/dev/null 2>&1 && pyright || true

start:
	[ -f package.json ] && npm start || true
	[ -f src/app.py ] && python -m src.app || true

check: fmt lint typecheck test  ## local gate before commit

# Unified LinkedIn Pipeline Orchestration
orchestration.worker:
	CELERY_BROKER_URL?=redis://localhost:6379/0 ; \
	CELERY_RESULT_BACKEND?=redis://localhost:6379/1 ; \
	celery -A apps.orchestration.celery_app:app worker -Q ingest,route,scrape.job,scrape.post --concurrency=$${CONCURRENCY:-4} --loglevel=info

orchestration.beat:
	CELERY_BROKER_URL?=redis://localhost:6379/0 ; \
	CELERY_RESULT_BACKEND?=redis://localhost:6379/1 ; \
	celery -A apps.orchestration.celery_app:app beat --loglevel=info

orchestration.monitor:
	CELERY_BROKER_URL?=redis://localhost:6379/0 ; \
	celery -A apps.orchestration.celery_app:app flower --port=5555

orchestration.pipeline:
	# One-shot pipeline trigger
	CELERY_BROKER_URL?=redis://localhost:6379/0 ; \
	CELERY_RESULT_BACKEND?=redis://localhost:6379/1 ; \
	celery -A apps.orchestration.celery_app:app call apps.orchestration.tasks.pipeline_chain

orchestration.start:
	@echo "Unified LinkedIn Pipeline:"
	@echo "  Terminal 1: make orchestration.worker"
	@echo "  Terminal 2: make orchestration.beat"
	@echo "  Optional monitoring: make orchestration.monitor"
	@echo "  One-shot test: make orchestration.pipeline"

test.e2e:
	# End-to-end pipeline test with real data
	@echo "Testing full pipeline with real Google Sheets..."
	@echo "This will:"
	@echo "  1. Ingest from real Google Sheets"
	@echo "  2. Import to database"
	@echo "  3. Classify links"
	@echo "  4. Route to scraper queues"
	@echo "Note: Requires running Celery worker and Redis/PostgreSQL"
	@echo ""
	LIVE_TESTS=1 pytest tests/live/test_ingest_live.py::test_live_full_import_and_classify -v -s

# Legacy scraper helpers (for backward compatibility during transition)
scraper.dev:
	# Usage: make scraper.dev URL="https://www.linkedin.com/jobs/view/..." [HEADED=true]
	"$$(pwd)/.venv/bin/python" -m src.scraper --url "$${URL}" $$( [ "$$${HEADED:-true}" = "true" ] && echo "--headed" )

scraper.test:
	[ -f pytest.ini -o -f pyproject.toml -o -d tests ] && pytest -q -k scraper || true

ci: lint typecheck test
