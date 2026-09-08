import asyncio
from types import SimpleNamespace

from app.services.bm25_store_service import BM25StoreService
from app.services.chunk_service import MarkdownChunk
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.knowledge_base_path_service import KnowledgeBasePathService
from app.services.project_knowledge_service import ProjectKnowledgeService
from app.services.vector_store_service import VectorStoreService


class StubEmbeddingService:
    async def embed_query(self, query: str) -> list[float]:
        return [1.0, 0.0]


class StubResourceRepository:
    def __init__(self, ready_file_ids: set[int]) -> None:
        self._ready_file_ids = ready_file_ids

    def list_ready_by_project(self, *, project_id: int):
        return [SimpleNamespace(id=file_id) for file_id in self._ready_file_ids]


def test_project_knowledge_search_returns_top_five_current_project_sources(tmp_path) -> None:
    paths = KnowledgeBasePathService(tmp_path / "knowledge_bases")
    chunks = [
        MarkdownChunk(
            f"chunk-{index}", 88, 9, "paper.md", f"协作学习 AI 素养 {index}", index
        )
        for index in range(6)
    ]
    vectors = VectorStoreService(paths)
    bm25 = BM25StoreService(paths)
    vectors.create_or_update_index(
        project_id=88,
        chunks=chunks,
        embeddings=[[1.0, 0.0] for _ in chunks],
    )
    bm25.create_or_update_index(project_id=88, chunks=chunks)
    hybrid = HybridRetrievalService(
        embedding_service=StubEmbeddingService(),  # type: ignore[arg-type]
        vector_store=vectors,
        bm25_store=bm25,
    )
    service = ProjectKnowledgeService(
        None,  # type: ignore[arg-type]
        hybrid_retrieval=hybrid,
        resource_repository=StubResourceRepository({9}),  # type: ignore[arg-type]
    )

    sources = asyncio.run(
        service.search(project_id=88, query="协作学习", top_k=5)
    )

    assert len(sources) == 5
    assert all(source.file_id == 9 for source in sources)
    assert all(source.filename == "paper.md" for source in sources)


def test_project_knowledge_search_returns_empty_without_ready_files() -> None:
    service = ProjectKnowledgeService(
        None,  # type: ignore[arg-type]
        resource_repository=StubResourceRepository(set()),  # type: ignore[arg-type]
    )

    assert asyncio.run(service.search(project_id=88, query="协作学习")) == []
