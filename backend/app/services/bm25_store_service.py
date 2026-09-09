"""Project-isolated, persisted BM25 keyword retrieval for local knowledge bases."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass

from app.services.chunk_service import MarkdownChunk
from app.services.knowledge_base_path_service import KnowledgeBasePathService


class BM25StoreError(RuntimeError):
    pass


class BM25IndexNotFoundError(BM25StoreError):
    pass


@dataclass(frozen=True)
class BM25SearchResult:
    chunk: MarkdownChunk
    score: float


class ProjectBM25Index:
    """Loaded BM25 corpus for a single project."""

    _K1 = 1.5
    _B = 0.75

    def __init__(self, chunks: list[MarkdownChunk]) -> None:
        if not chunks:
            raise BM25StoreError("at least one chunk is required to build a BM25 index")
        self.chunks = chunks
        self._documents = [_tokenize(chunk.content) for chunk in chunks]
        self._document_lengths = [len(document) for document in self._documents]
        if not all(self._document_lengths):
            raise BM25StoreError("BM25 chunks must contain searchable text")
        self._average_length = sum(self._document_lengths) / len(self._documents)
        self._document_frequency = Counter(
            token for document in self._documents for token in set(document)
        )

    def keyword_search(
        self,
        query: str,
        top_k: int,
        allowed_file_ids: set[int] | None = None,
    ) -> list[BM25SearchResult]:
        if not isinstance(top_k, int) or top_k <= 0:
            raise BM25StoreError("top_k must be a positive integer")
        query_tokens = _tokenize(query)
        if not query_tokens:
            raise BM25StoreError("query must contain searchable text")

        total_documents = len(self._documents)
        scored: list[BM25SearchResult] = []
        for index, document in enumerate(self._documents):
            if (
                allowed_file_ids is not None
                and self.chunks[index].file_id not in allowed_file_ids
            ):
                continue
            frequencies = Counter(document)
            score = 0.0
            for token in query_tokens:
                document_frequency = self._document_frequency.get(token, 0)
                if document_frequency == 0:
                    continue
                inverse_frequency = math.log(
                    1 + (total_documents - document_frequency + 0.5)
                    / (document_frequency + 0.5)
                )
                term_frequency = frequencies[token]
                denominator = term_frequency + self._K1 * (
                    1
                    - self._B
                    + self._B * self._document_lengths[index] / self._average_length
                )
                score += inverse_frequency * term_frequency * (self._K1 + 1) / denominator
            if score > 0:
                scored.append(BM25SearchResult(chunk=self.chunks[index], score=score))
        return sorted(scored, key=lambda result: result.score, reverse=True)[:top_k]


class BM25StoreService:
    """Persist one JSON-backed BM25 corpus per project without external services."""

    def __init__(self, paths: KnowledgeBasePathService | None = None) -> None:
        self._paths = paths or KnowledgeBasePathService()

    def create_or_update_index(
        self, *, project_id: int, chunks: list[MarkdownChunk]
    ) -> ProjectBM25Index:
        if not chunks:
            raise BM25StoreError("at least one chunk is required to create an index")
        if any(chunk.project_id != project_id for chunk in chunks):
            raise BM25StoreError("all chunks must belong to the target project")

        try:
            existing = self.load_index(project_id)
        except BM25IndexNotFoundError:
            existing = None
        merged = {chunk.chunk_id: chunk for chunk in (existing.chunks if existing else [])}
        merged.update({chunk.chunk_id: chunk for chunk in chunks})
        project_index = ProjectBM25Index(list(merged.values()))
        self._save_index(project_id, project_index)
        return project_index

    def load_index(self, project_id: int) -> ProjectBM25Index:
        index_path = self._paths.bm25_index_file(project_id)
        if not index_path.is_file():
            raise BM25IndexNotFoundError(
                f"No local BM25 index exists for project {project_id}"
            )
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            chunks = [MarkdownChunk(**item) for item in payload["chunks"]]
            return ProjectBM25Index(chunks)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise BM25StoreError("Unable to load the local project BM25 index") from exc

    def keyword_search(
        self,
        *,
        project_id: int,
        query: str,
        top_k: int,
        allowed_file_ids: set[int] | None = None,
    ) -> list[BM25SearchResult]:
        return self.load_index(project_id).keyword_search(
            query, top_k, allowed_file_ids=allowed_file_ids
        )

    def _save_index(self, project_id: int, project_index: ProjectBM25Index) -> None:
        index_path = self._paths.bm25_index_file(project_id)
        temporary_path = index_path.with_suffix(".json.tmp")
        try:
            temporary_path.write_text(
                json.dumps(
                    {"version": 1, "chunks": [asdict(chunk) for chunk in project_index.chunks]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            temporary_path.replace(index_path)
        except OSError as exc:
            raise BM25StoreError("Unable to persist the local project BM25 index") from exc
        finally:
            temporary_path.unlink(missing_ok=True)


_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[a-z0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    if not isinstance(text, str):
        return []
    return _TOKEN_PATTERN.findall(text.lower())
