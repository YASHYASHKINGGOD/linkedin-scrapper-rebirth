# Project memory & rules (Claude + Warp)

Read order: WARP.md → DESIGN.md → planning.md → tasks.md → README.md.

## Goals
- One-command bootstrap & test on any machine
- Small design before implementation; acceptance criteria defined
- Every change updates tests and docs

## Code standards
- Runtimes pinned by .tool-versions / .nvmrc
- Style: Prettier/ESLint (JS), Black/Ruff (Py); types via tsc/mypy/pyright
- Branches: feat/<slug>, fix/<slug>, chore/<slug>
- Commits: Conventional Commits

## Commands
- Bootstrap: make setup
- Dev: make dev
- Run: make start
- Format: make fmt | Lint: make lint | Types: make typecheck
- Tests: make test
- Gate: make check

## Work protocol (each session)
1) Read docs above and restate the next task
2) Implement in small commits; keep make check green
3) Update tasks.md; copy SESSION_TEMPLATE.md → sessions/SESSION-YYYY-MM-DD.md with exact commands run
4) Append a “Session YYYY-MM-DD” note here

## Project specifics
- Architecture: Ingest → Classify → Scrape (bronze) → Stage (silver) → Extract LLM (gold) → Route
- Data model: see DESIGN.md (Postgres 14+ DDL provided)
- Queues: ingest.links, scrape.job, scrape.post, extract.llm, route.build, dead.letter
- SLOs: p95 ingest→job <10m; 95%+ valid extraction daily; zero dupes/24h

## Do not
- Rely on chat memory; treat repo as the source of truth
- Add hidden manual steps; everything via scripts/Make targets
