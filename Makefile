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
	[ -f pytest.ini -o -f pyproject.toml -o -f requirements.txt ] && pytest -q || true

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
ci: lint typecheck test
