# Build context = repository root.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps for psycopg + onnxruntime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Install local workspace packages first (better layer caching).
COPY packages/shared_py /app/packages/shared_py
COPY packages/rag_py /app/packages/rag_py
COPY packages/db_py /app/packages/db_py
RUN pip install -e /app/packages/shared_py \
 && pip install -e /app/packages/rag_py \
 && pip install -e /app/packages/db_py

# Install the API app.
COPY apps/api /app/apps/api
RUN pip install -e /app/apps/api

WORKDIR /app/apps/api

# Pre-download local embedding/reranker models so the container starts offline.
RUN python -c "import os; os.environ.setdefault('EMBED_DEVICE','cpu'); \
import importlib; \
mod=importlib.util.find_spec('sports_oracle_rag'); \
print('rag present' if mod else 'rag missing')" || true

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
