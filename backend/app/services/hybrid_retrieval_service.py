"""Local FAISS + BM25 hybrid retrieval for project knowledge bases."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.services.bm25_store_service import (
    BM25IndexNotFoundError,
    BM25StoreService,
)
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import (
    VectorIndexNotFoundError,
    VectorStoreService,
)


class HybridRetrievalError(RuntimeError):
    pass


class HybridRetrievalIndexNotFoundError(HybridRetrievalError):
    pass


@dataclass(frozen=True)
class HybridSearchResult:
    content: str
    filename: str
    file_id: int
    chunk_id: str
    chunk_index: int
    score: float


class HybridRetrievalService:
    """Fuse semantic and lexical rankings with Reciprocal Rank Fusion.

    This service has no Agent or Spark dependency.  Embeddings come only from
    the existing vendor-neutral :class:`EmbeddingService` boundary.
    """

    def __init__(
        self,
        *,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStoreService | None = None,
        bm25_store: BM25StoreService | None = None,
        candidate_k: int | None = None,
        top_k: int | None = None,
        rrf_k: int | None = None,
    ) -> None:
        self._embedding_service = embedding_service or EmbeddingService()
        self._vector_store = vector_store or VectorStoreService()
        self._bm25_store = bm25_store or BM25StoreService()
        self._candidate_k = (
            settings.knowledge_base_retrieval_candidate_k
            if candidate_k is None
            else candidate_k
        )
        self._top_k = (
            settings.knowledge_base_retrieval_top_k if top_k is None else top_k
        )
        self._rrf_k = settings.knowledge_base_rrf_k if rrf_k is None else rrf_k
        if self._candidate_k <= 0 or self._top_k <= 0 or self._rrf_k < 0:
            raise ValueError("hybrid retrieval limits must be positive")

    async def search(
        self,
        *,
        project_id: int,
        query: str,
        top_k: int | None = None,
        allowed_file_ids: set[int] | None = None,
    ) -> list[HybridSearchResult]:
        """Retrieve FAISS Top-N and BM25 Top-N, then return RRF-ranked chunks."""
        effective_top_k = self._top_k if top_k is None else top_k
        if not isinstance(effective_top_k, int) or effective_top_k <= 0:
            raise HybridRetrievalError("top_k must be a positive integer")
        if not isinstance(query, str) or not query.strip():
            raise HybridRetrievalError("query is required")

        semantic_results = []
        keyword_results = []
        try:
            query_embedding = await self._embedding_service.embed_query(query)
            vector_options = {
                "project_id": project_id,
                "query_embedding": query_embedding,
                "top_k": self._candidate_k,
            }
            if allowed_file_ids is not None:
                vector_options["allowed_file_ids"] = allowed_file_ids
            semantic_results = self._vector_store.search(**vector_options)
        except VectorIndexNotFoundError:
            pass

        try:
            keyword_options = {
                "project_id": project_id,
                "query": query,
                "top_k": self._candidate_k,
            }
            if allowed_file_ids is not None:
                keyword_options["allowed_file_ids"] = allowed_file_ids
            keyword_results = self._bm25_store.keyword_search(**keyword_options)
        except BM25IndexNotFoundError:
            pass

        if not semantic_results and not keyword_results:
            raise HybridRetrievalIndexNotFoundError(
                f"No local retrieval index exists for project {project_id}"
            )

        merged: dict[str, HybridSearchResult] = {}
        for ranked_results in (semantic_results, keyword_results):
            for rank, result in enumerate(ranked_results, start=1):
                chunk = result.chunk
                contribution = 1 / (self._rrf_k + rank)
                existing = merged.get(chunk.chunk_id)
                if existing is None:
                    merged[chunk.chunk_id] = HybridSearchResult(
                        content=chunk.content,
                        filename=chunk.filename,
                        file_id=chunk.file_id,
                        chunk_id=chunk.chunk_id,
                        chunk_index=chunk.chunk_index,
                        score=contribution,
                    )
                else:
                    merged[chunk.chunk_id] = HybridSearchResult(
                        content=existing.content,
                        filename=existing.filename,
                        file_id=existing.file_id,
                        chunk_id=existing.chunk_id,
                        chunk_index=existing.chunk_index,
                        score=existing.score + contribution,
                    )
        return sorted(merged.values(), key=lambda result: result.score, reverse=True)[
            :effective_top_k
        ]
