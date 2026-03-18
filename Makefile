.PHONY: install seed run run-continuous test docker-build docker-run docker-seed help

# ── Variables ──────────────────────────────────────────────────────────────────
PYTHON      ?= python3
PIP         ?= pip
IMAGE_NAME  ?= ai_video_pipeline
COMPOSE     ?= docker compose

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Local development ──────────────────────────────────────────────────────────

install:  ## Install Python dependencies
	$(PIP) install -r requirements.txt

seed:  ## Seed the DB with default stock symbols (requires PG_CONNECTION_STRING)
	$(PYTHON) seed_stocks.py

run:  ## Run one pipeline batch (requires PG_CONNECTION_STRING)
	$(PYTHON) main.py

run-continuous:  ## Run the pipeline in continuous polling mode
	$(PYTHON) main.py --continuous

test:  ## Run the unit tests
	$(PYTHON) -m pytest tests/ -v

# ── Docker ─────────────────────────────────────────────────────────────────────

docker-build:  ## Build the Docker image
	$(COMPOSE) build

docker-run:  ## Run one pipeline batch inside Docker (reads .env)
	$(COMPOSE) run --rm pipeline

docker-seed:  ## Seed the DB from inside Docker
	$(COMPOSE) --profile seed run --rm seed

docker-continuous:  ## Start the long-running continuous pipeline service
	$(COMPOSE) --profile continuous up -d pipeline-continuous
