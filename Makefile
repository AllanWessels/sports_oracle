.PHONY: help up up-gpu down build logs seed ingest test lint fmt ps

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Build + run the full stack (CPU; GPU auto-detected at runtime)
	docker compose up --build

up-gpu: ## Run the stack with the NVIDIA GPU overlay
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build

down: ## Stop the stack
	docker compose down

build: ## Build all images
	docker compose build

logs: ## Tail logs
	docker compose logs -f

ps: ## Show running services
	docker compose ps

seed: ## Load the reference-docs corpus into Qdrant
	docker compose run --rm ingest-worker python -m jobs.reference_docs

ingest: ## Run a one-off news ingestion pass
	docker compose run --rm ingest-worker python -m jobs.news

test: ## Run all python test suites
	docker compose run --rm api pytest -q

lint: ## Lint python with ruff + mypy
	docker compose run --rm api sh -c "ruff check . && mypy app"

fmt: ## Auto-format python with ruff
	docker compose run --rm api ruff format .
