"""LangChain-compatible embeddings backed by the project's local fastembed.

RAGAS needs an embeddings model for answer_relevancy / context metrics. Project
rule: never call a paid embedding API. This adapter reuses ``rag_py``'s local
fastembed dense encoder so eval stays offline and consistent with retrieval.

``rag_py`` (and thus fastembed) is imported lazily so importing this module —
and the eval package's unit tests — does not pull the heavy ML stack.
"""

from __future__ import annotations

from typing import Any


class FastEmbedEmbeddings:
    """Minimal ``langchain_core.embeddings.Embeddings`` duck-type.

    Implements ``embed_documents`` / ``embed_query`` over
    ``sports_oracle_rag.embeddings.embed_dense``.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        from sports_oracle_rag.embeddings import embed_dense

        return embed_dense(list(texts))

    def embed_query(self, text: str) -> list[float]:
        from sports_oracle_rag.embeddings import embed_dense

        return embed_dense([text])[0]

    # RAGAS sometimes calls async variants; delegate to the sync impl.
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)


def ragas_embeddings() -> Any:
    """Return the local embeddings wrapped for RAGAS (lazy import of ragas)."""
    from ragas.embeddings import LangchainEmbeddingsWrapper

    return LangchainEmbeddingsWrapper(FastEmbedEmbeddings())
