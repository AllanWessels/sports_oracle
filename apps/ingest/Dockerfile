# Build context: REPO ROOT
# docker build -f apps/ingest/Dockerfile .

FROM python:3.11-slim AS base

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------------
# Install shared_py, rag_py, then the ingest app
# ---------------------------------------------------------------------------
COPY packages/shared_py /app/packages/shared_py
COPY packages/rag_py    /app/packages/rag_py
COPY apps/ingest        /app/apps/ingest

RUN pip install --no-cache-dir /app/packages/shared_py
RUN pip install --no-cache-dir /app/packages/rag_py
RUN pip install --no-cache-dir /app/apps/ingest

# ---------------------------------------------------------------------------
# Bake fastembed models into the image so containers start offline.
# The import + instantiation triggers model download during build.
# ---------------------------------------------------------------------------
RUN python - <<'PYEOF'
import logging
logging.basicConfig(level=logging.INFO)
import os
# Force CPU at build time (no GPU in build environment)
os.environ.setdefault("EMBED_DEVICE", "cpu")
# Instantiate all three encoders to trigger model download + caching
from sports_oracle_rag.embeddings import get_dense_encoder, get_sparse_encoder, get_reranker
print("Downloading dense encoder...")
get_dense_encoder()
print("Downloading sparse encoder...")
get_sparse_encoder()
print("Downloading reranker...")
get_reranker()
print("All models cached successfully.")
PYEOF

# ---------------------------------------------------------------------------
# Copy reference data
# ---------------------------------------------------------------------------
COPY data /app/data

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
WORKDIR /app/apps/ingest

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/apps/ingest

CMD ["python", "worker.py"]
