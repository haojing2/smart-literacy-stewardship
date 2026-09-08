from app.services.bm25_store_service import BM25StoreService
from app.services.chunk_service import MarkdownChunk
from app.services.knowledge_base_path_service import KnowledgeBasePathService


def test_bm25_index_persists_and_searches_project_chunks(tmp_path) -> None:
    paths = KnowledgeBasePathService(tmp_path / "knowledge_bases")
    service = BM25StoreService(paths)
    chunks = [
        MarkdownChunk("chunk-a", 17, 1, "paper.md", "协作学习促进人工智能素养", 0),
        MarkdownChunk("chunk-b", 17, 1, "paper.md", "课堂评价量规设计", 1),
    ]

    service.create_or_update_index(project_id=17, chunks=chunks)
    results = service.load_index(17).keyword_search("协作学习", 1)

    assert results[0].chunk.chunk_id == "chunk-a"
    assert results[0].chunk.file_id == 1
    assert (tmp_path / "knowledge_bases" / "project_17" / "index" / "bm25.json").is_file()


def test_bm25_index_updates_the_same_chunk_id(tmp_path) -> None:
    service = BM25StoreService(KnowledgeBasePathService(tmp_path / "knowledge_bases"))
    service.create_or_update_index(
        project_id=17,
        chunks=[MarkdownChunk("chunk-a", 17, 1, "paper.md", "old", 0)],
    )
    index = service.create_or_update_index(
        project_id=17,
        chunks=[MarkdownChunk("chunk-a", 17, 1, "paper.md", "new strategy", 0)],
    )

    assert index.chunks[0].content == "new strategy"
