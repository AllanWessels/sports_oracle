.PHONY: help up up-gpu down build logs seed ingest test lint fmt ps eval migrate

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Build + run the full stack (CPU; GPU auto-detected at runtime)
	docker compose up --build

up-gpu: ## Run the stack with the NVIDIA GPU overlay (CUDA embeddings + web on :5173)
	docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.gpu.yml up --build

down: ## Stop the stack
	docker compose down

build: ## Build all images
	docker compose build

logs: ## Tail logs
	docker compose logs -f

ps: ## Show running services
	docker compose ps

migrate: ## Apply DB migrations (creates app tables incl. eval_traces)
	docker compose run --rm -w /app/packages/db_py api alembic upgrade head

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

# Eval scorecard over the golden set. Self-contained (mounts the repo into a
# clean python image, installs the workspace packages in dependency order).
# Export ANTHROPIC_API_KEY for the RAGAS judge, or pass EVAL_ARGS=--citations-only.
eval: ## Run the eval scorecard over the golden set (export ANTHROPIC_API_KEY)
	docker run --rm -v "$(PWD)":/repo -w /repo \
	  -e ANTHROPIC_API_KEY -e MODEL_EVAL python:3.11-slim sh -lc '\
	    pip install -q -e packages/shared_py -e packages/rag_py -e "packages/eval_py[ragas]" && \
	    python -m sports_oracle_eval.run $(EVAL_ARGS)'
