"""Project-isolated local FAISS storage for future knowledge-base retrieval."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from app.services.chunk_service import MarkdownChunk
from app.services.knowledge_base_path_service import KnowledgeBasePathService


class VectorStoreError(RuntimeError):
    pass


class VectorIndexNotFoundError(VectorStoreError):
    pass


@dataclass(frozen=True)
class VectorSearchResult:
    chunk: MarkdownChunk
    score: float


@dataclass
class ProjectVectorIndex:
    """Loaded project index with metadata kept in FAISS row order."""

    index: Any
    chunks: list[MarkdownChunk]

    def search(
        self, query_embedding: list[float], top_k: int
    ) -> list[VectorSearchResult]:
        if not isinstance(top_k, int) or top_k <= 0:
            raise VectorStoreError("top_k must be a positive integer")
        vector = _normalize_vectors([query_embedding])
        scores, ids = self.index.search(vector, min(top_k, len(self.chunks)))
        results: list[VectorSearchResult] = []
        for score, vector_id in zip(scores[0], ids[0], strict=True):
            if vector_id < 0:
                continue
            results.append(
                VectorSearchResult(
                    chunk=self.chunks[int(vector_id)],
                    score=float(score),
                )
            )
        return results


class VectorStoreService:
    """Persist one FAISS cosine-similarity index per project directory.

    The service stores vectors only in local FAISS files and metadata only in
    local JSON. It never invokes an embedding provider, Spark, or MySQL.
    """

    def __init__(self, paths: KnowledgeBasePathService | None = None) -> None:
        self._paths = paths or KnowledgeBasePathService()

    def create_or_update_index(
        self,
        *,
        project_id: int,
        chunks: list[MarkdownChunk],
        embeddings: list[list[float]],
    ) -> ProjectVectorIndex:
        if len(chunks) != len(embeddings):
            raise VectorStoreError("chunks and embeddings must have the same length")
        if not chunks:
            raise VectorStoreError("at least one chunk is required to create an index")
        if any(chunk.project_id != project_id for chunk in chunks):
            raise VectorStoreError("all chunks must belong to the target project")

        incoming_vectors = _normalize_vectors(embeddings)
        incoming = {chunk.chunk_id: (chunk, incoming_vectors[index]) for index, chunk in enumerate(chunks)}

        try:
            loaded = self.load_index(project_id)
        except VectorIndexNotFoundError:
            loaded = None

        if loaded is not None:
            existing_vectors = _reconstruct_vectors(loaded.index, len(loaded.chunks))
            merged: dict[str, tuple[MarkdownChunk, Any]] = {
                chunk.chunk_id: (chunk, existing_vectors[index])
                for index, chunk in enumerate(loaded.chunks)
            }
            merged.update(incoming)
        else:
            merged = incoming

        merged_chunks = [item[0] for item in merged.values()]
        merged_vectors = _stack_vectors([item[1] for item in merged.values()])
        faiss = _load_faiss()
        index = faiss.IndexFlatIP(int(merged_vectors.shape[1]))
        index.add(merged_vectors)
        project_index = ProjectVectorIndex(index=index, chunks=merged_chunks)
        self._save_index(project_id, project_index)
        return project_index

    def load_index(self, project_id: int) -> ProjectVectorIndex:
        index_path = self._paths.faiss_index_file(project_id)
        metadata_path = self._paths.faiss_metadata_file(project_id)
        if not index_path.is_file() or not metadata_path.is_file():
            raise VectorIndexNotFoundError(
                f"No local vector index exists for project {project_id}"
            )
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            chunks = [MarkdownChunk(**item) for item in metadata["chunks"]]
            index = _load_faiss().read_index(str(index_path))
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            raise VectorStoreError("Unable to load the local project vector index") from exc
        if index.ntotal != len(chunks):
            raise VectorStoreError("FAISS index and chunk metadata are inconsistent")
        return ProjectVectorIndex(index=index, chunks=chunks)

    def search(
        self,
        *,
        project_id: int,
        query_embedding: list[float],
        top_k: int,
    ) -> list[VectorSearchResult]:
        return self.load_index(project_id).search(query_embedding, top_k)

    def _save_index(self, project_id: int, project_index: ProjectVectorIndex) -> None:
        index_path = self._paths.faiss_index_file(project_id)
        metadata_path = self._paths.faiss_metadata_file(project_id)
        temporary_index = index_path.with_suffix(".faiss.tmp")
        temporary_metadata = metadata_path.with_suffix(".json.tmp")
        try:
            _load_faiss().write_index(project_index.index, str(temporary_index))
            temporary_metadata.write_text(
                json.dumps(
                    {"version": 1, "chunks": [asdict(chunk) for chunk in project_index.chunks]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            temporary_index.replace(index_path)
            temporary_metadata.replace(metadata_path)
        except OSError as exc:
            raise VectorStoreError("Unable to persist the local project vector index") from exc
        finally:
            temporary_index.unlink(missing_ok=True)
            temporary_metadata.unlink(missing_ok=True)


def _load_faiss() -> Any:
    try:
        import faiss
    except ImportError as exc:
        raise VectorStoreError("faiss-cpu is required for local vector storage") from exc
    return faiss


def _normalize_vectors(vectors: list[list[float]]) -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise VectorStoreError("numpy is required for local vector storage") from exc
    try:
        array = np.asarray(vectors, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise VectorStoreError("embedding vectors must contain numeric values") from exc
    if array.ndim != 2 or array.shape[0] == 0 or array.shape[1] == 0:
        raise VectorStoreError("embedding vectors must be a non-empty two-dimensional list")
    if not np.isfinite(array).all():
        raise VectorStoreError("embedding vectors must contain finite values")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if (norms == 0).any():
        raise VectorStoreError("embedding vectors must not be zero vectors")
    return array / norms


def _reconstruct_vectors(index: Any, count: int) -> Any:
    if count == 0:
        raise VectorStoreError("cannot update an empty FAISS index")
    return index.reconstruct_n(0, count)


def _stack_vectors(vectors: list[Any]) -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise VectorStoreError("numpy is required for local vector storage") from exc
    dimensions = {vector.shape[0] for vector in vectors}
    if len(dimensions) != 1:
        raise VectorStoreError("all embeddings in one project index must have the same dimension")
    return np.asarray(vectors, dtype=np.float32)
