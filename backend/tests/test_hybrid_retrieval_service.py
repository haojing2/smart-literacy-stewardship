import asyncio

from app.services.bm25_store_service import BM25StoreService
from app.services.chunk_service import MarkdownChunk
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.knowledge_base_path_service import KnowledgeBasePathService
from app.services.vector_store_service import VectorStoreService


class StubEmbeddingService:
    async def embed_query(self, query: str) -> list[float]:
        return [1.0, 0.0]


def test_hybrid_retrieval_fuses_faiss_and_bm25_and_deduplicates_chunks(tmp_path) -> None:
    paths = KnowledgeBasePathService(tmp_path / "knowledge_bases")
    chunks = [
        MarkdownChunk("shared", 42, 3, "paper.md", "协作学习支持AI素养", 0),
        MarkdownChunk("semantic", 42, 3, "paper.md", "课堂互动策略", 1),
        MarkdownChunk("keyword", 42, 4, "second.md", "协作学习活动设计", 0),
    ]
    vectors = VectorStoreService(paths)
    bm25 = BM25StoreService(paths)
    vectors.create_or_update_index(
        project_id=42,
        chunks=chunks,
        embeddings=[[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]],
    )
    bm25.create_or_update_index(project_id=42, chunks=chunks)
    service = HybridRetrievalService(
        embedding_service=StubEmbeddingService(),  # type: ignore[arg-type]
        vector_store=vectors,
        bm25_store=bm25,
        candidate_k=10,
        top_k=5,
        rrf_k=60,
    )

    results = asyncio.run(service.search(project_id=42, query="协作学习"))

    assert results[0].chunk_id == "shared"
    assert len({result.chunk_id for result in results}) == len(results)
    assert results[0].filename == "paper.md"
    assert results[0].file_id == 3
    assert results[0].chunk_index == 0
    assert results[0].score > 0
