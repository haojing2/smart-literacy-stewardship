from app.services.chunk_service import MarkdownChunk
from app.services.knowledge_base_path_service import KnowledgeBasePathService
from app.services.vector_store_service import VectorStoreService


def test_project_faiss_index_persists_metadata_and_can_be_reloaded(tmp_path) -> None:
    service = VectorStoreService(KnowledgeBasePathService(tmp_path / "knowledge_bases"))
    chunks = [
        MarkdownChunk("chunk-a", 17, 1, "paper.md", "collaborative learning", 0),
        MarkdownChunk("chunk-b", 17, 1, "paper.md", "assessment rubric", 1),
    ]

    service.create_or_update_index(
        project_id=17,
        chunks=chunks,
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
    )
    loaded = service.load_index(17)
    results = loaded.search([0.9, 0.1], top_k=1)

    assert results[0].chunk.chunk_id == "chunk-a"
    assert results[0].chunk.project_id == 17
    assert results[0].chunk.filename == "paper.md"
    assert (tmp_path / "knowledge_bases" / "project_17" / "index" / "index.faiss").is_file()
    assert (tmp_path / "knowledge_bases" / "project_17" / "index" / "metadata.json").is_file()


def test_project_faiss_index_updates_existing_chunk_id(tmp_path) -> None:
    service = VectorStoreService(KnowledgeBasePathService(tmp_path / "knowledge_bases"))
    original = MarkdownChunk("chunk-a", 17, 1, "paper.md", "original", 0)
    updated = MarkdownChunk("chunk-a", 17, 1, "paper.md", "updated", 0)
    service.create_or_update_index(
        project_id=17, chunks=[original], embeddings=[[1.0, 0.0]]
    )
    index = service.create_or_update_index(
        project_id=17, chunks=[updated], embeddings=[[0.0, 1.0]]
    )

    assert index.chunks == [updated]
