# Makefile
.PHONY: setup dev build test lint fmt typecheck start check ci

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

# Scraper (Playwright) workers and dev helpers
scraper.worker:
	SCRAPER_CONCURRENCY?=1 ; \
	QUEUES?=scrape.job,scrape.post ; \
	CELERY_BROKER_URL?=redis://localhost:6379/0 ; \
	CELERY_RESULT_BACKEND?=redis://localhost:6379/1 ; \
	celery -A src.scraper.celery_app:app worker -Q $${QUEUES} --concurrency=$${SCRAPER_CONCURRENCY} --loglevel=info

scraper.dev:
	# Usage: make scraper.dev URL="https://www.linkedin.com/jobs/view/..." [HEADED=true]
	HEADED?=true ; \
	"$$(pwd)/.venv/bin/python" -m src.scraper.dev --url "$${URL}" $$( [ "$${HEADED}" = "true" ] && echo "--headed" )

scraper.test:
	[ -f pytest.ini -o -f pyproject.toml -o -d tests ] && pytest -q -k scraper || true

ci: lint typecheck test
