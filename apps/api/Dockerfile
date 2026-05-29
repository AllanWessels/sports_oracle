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
COPY packages/eval_py /app/packages/eval_py
RUN pip install -e /app/packages/shared_py \
 && pip install -e /app/packages/rag_py \
 && pip install -e /app/packages/db_py \
 && pip install -e /app/packages/eval_py

# Install the API app.
COPY apps/api /app/apps/api
RUN pip install -e /app/apps/api

WORKDIR /app/apps/api

# Bake the embedding/reranker models into the image so the FIRST query doesn't
# pay a multi-minute cold download. Instantiating each encoder triggers the
# model fetch + cache at build time (the previous find_spec check was a no-op).
RUN python -c "import os; os.environ.setdefault('EMBED_DEVICE','cpu'); \
from sports_oracle_rag.embeddings import get_dense_encoder, get_sparse_encoder, get_reranker; \
get_dense_encoder(); get_sparse_encoder(); get_reranker(); \
print('embedding models cached')"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
