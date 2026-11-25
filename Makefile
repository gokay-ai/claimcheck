.DEFAULT_GOAL := help
BACKEND_PORT ?= 8791

.PHONY: help setup backend frontend test lint e2e screenshots diagram build docker corpus record eval-report

help: ## List the available targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && bun install

backend: ## Run the API on port 8791 (recorded demo unless OPENROUTER_API_KEY is set)
	cd backend && uv run uvicorn claimcheck.api:app_factory --factory --host 127.0.0.1 --port $(BACKEND_PORT)

frontend: ## Run the web interface on port 5191
	cd frontend && bun run dev

test: ## Run the backend and frontend unit tests
	cd backend && uv run pytest -q
	cd frontend && bun run test

lint: ## Lint, format-check and type-check both halves
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy
	cd frontend && bun run lint && bun run typecheck && bunx prettier --check "src/**/*.{ts,tsx,css}" "e2e/**/*.ts"

e2e: ## Run the browser tests against the recorded demo
	cd frontend && bunx playwright test

screenshots: ## Regenerate the storyboard frames and figures in docs/storyboards
	cd frontend && SCREENSHOTS=1 bunx playwright test
	python3 scripts/build_storyboards.py
	cd frontend && for f in ../docs/storyboards/storyboard-?-?.html; do node ../scripts/render_png.mjs $$f $${f%.html}.png 1400 0; done

diagram: ## Regenerate docs/architecture.svg and its PNG
	python3 scripts/draw_architecture.py
	cd frontend && node ../scripts/render_png.mjs ../docs/architecture.svg ../docs/architecture.png 1040 1368

build: ## Build the web interface into frontend/dist
	cd frontend && bun run build

docker: ## Build and run the single container on port 8080
	docker compose up --build

corpus: ## Rebuild the readings from Wikipedia (changes the pinned revisions)
	python3 scripts/build_corpus.py

record: ## Re-record the example answers (needs OPENROUTER_API_KEY)
	cd backend && uv run python ../scripts/record_replay.py

eval-report: ## Recompute the pilot measures from the stored runs and labels
	cd backend && uv sync --group plots && uv run claimcheck-eval report --dir ../evaluation
