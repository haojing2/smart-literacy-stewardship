from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.agents.research.errors import ResearchAgentContractError
from app.agents.research.spark_research_agent import SparkResearchAgent
from app.core.config import settings
from app.schemas.research_assistant import ResearchAnalysisRequest
from app.services.bm25_store_service import BM25StoreService
from app.services.chunk_service import MarkdownChunk
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.knowledge_base_path_service import KnowledgeBasePathService
from app.services.project_knowledge_service import ProjectKnowledgeService, ProjectKnowledgeSource
from app.services.research_chat_service import ResearchChatService
from app.services.vector_store_service import VectorStoreService


class FakeAgentClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.requests: list[list[dict[str, str]]] = []

    async def generate(self, messages):
        self.requests.append(messages)
        return self.responses.pop(0)


def test_validation_error_produces_specific_repair_prompt_and_final_contract_error() -> None:
    client = FakeAgentClient(['{"participants":[]}', '{"participants":[]}'])
    with pytest.raises(ResearchAgentContractError) as caught:
        asyncio.run(
            SparkResearchAgent(client=client).analyze_research(
                ResearchAnalysisRequest(resource_id=1, analysis_evidence="evidence")
            )
        )
    assert type(caught.value.__cause__).__name__ == "ValidationError"
    repair = client.requests[1][-1]["content"]
    assert "participants" in repair
    assert "extra" in repair
    assert "resultSchema" in repair


class StubDb:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FailingProvider:
    async def analyze_research(self, request):
        raise ResearchAgentContractError("invalid contract")


class SessionRepository:
    def __init__(self) -> None:
        self.analysis_data = None

    def get_owned_project(self, **kwargs):
        return SimpleNamespace(id=1020, title="Project", topic="Topic")

    def get_owned_project_resource(self, **kwargs):
        return SimpleNamespace(
            id=16, project_id=1020, processing_status="TEXT_EXTRACTED",
            index_status="ready", extracted_text="full paper must not be sent",
            original_filename="paper.pdf", media_type="application/pdf", sha256="a" * 64,
        )

    def get_latest_analysis(self, **kwargs):
        return None

    def create_analysis(self, **kwargs):
        self.analysis_data = kwargs["structured_data"]
        return SimpleNamespace(id=41)

    def create_session(self, **kwargs):
        return SimpleNamespace(id=51)


class OneSourceKnowledge:
    async def search_resource(self, *, project_id, file_id, query, top_k):
        return [
            ProjectKnowledgeSource(
                content="bounded evidence", project_id=project_id, filename="paper.pdf",
                file_id=file_id, chunk_id="only-file-16", chunk_index=0, score=1.0,
            )
        ]


def test_structured_analysis_failure_still_creates_incomplete_session() -> None:
    db = StubDb()
    service = ResearchChatService(db, FailingProvider(), OneSourceKnowledge())  # type: ignore[arg-type]
    repository = SessionRepository()
    service.repository = repository  # type: ignore[assignment]
    service.get_session = lambda **kwargs: SimpleNamespace(session_id=51)  # type: ignore[method-assign]
    response = asyncio.run(
        service.create_session(
            current_user_id=1, project_id=1020,
            request=SimpleNamespace(resource_id=16, title=None),
        )
    )
    assert response.session_id == 51
    assert repository.analysis_data["evidence_ready"] is False
    assert repository.analysis_data["research_subjects"] == []
    assert db.commits == 1


def test_bounded_evidence_respects_chunk_and_character_limits(monkeypatch) -> None:
    class ManySources:
        async def search_resource(self, *, project_id, file_id, query, top_k):
            return [
                ProjectKnowledgeSource(
                    content="x" * 200, project_id=project_id, filename="paper.pdf",
                    file_id=file_id, chunk_id=f"{query}-{index}", chunk_index=index,
                    score=1 / (index + 1),
                )
                for index in range(5)
            ]

    monkeypatch.setattr(settings, "research_analysis_max_chunks", 4)
    monkeypatch.setattr(settings, "research_analysis_max_context_chars", 600)
    service = ResearchChatService(None, SimpleNamespace(), ManySources())  # type: ignore[arg-type]
    evidence, sources, retrieved_count = asyncio.run(
        service._prepare_analysis_evidence(project_id=1020, file_id=16)
    )
    assert retrieved_count == 30
    assert len(sources) <= 4
    assert len(evidence) <= 600
    assert all(source.file_id == 16 for source in sources)


def test_search_resource_filters_before_top_k_with_two_files(tmp_path) -> None:
    paths = KnowledgeBasePathService(tmp_path)
    chunks = [
        MarkdownChunk(f"b-{i}", 1, 20, "b.md", "target", i) for i in range(5)
    ] + [MarkdownChunk("a-0", 1, 10, "a.md", "target", 0)]
    vectors = VectorStoreService(paths)
    bm25 = BM25StoreService(paths)
    vectors.create_or_update_index(project_id=1, chunks=chunks, embeddings=[[1.0, 0.0]] * 6)
    bm25.create_or_update_index(project_id=1, chunks=chunks)

    class Embed:
        async def embed_query(self, query):
            return [1.0, 0.0]

    class Resources:
        def get_by_id_and_project(self, **kwargs):
            return SimpleNamespace(id=10, index_status="ready")

    service = ProjectKnowledgeService(
        None,
        hybrid_retrieval=HybridRetrievalService(
            embedding_service=Embed(), vector_store=vectors, bm25_store=bm25,
            candidate_k=2, top_k=2,
        ),
        resource_repository=Resources(),
    )
    results = asyncio.run(
        service.search_resource(project_id=1, file_id=10, query="target", top_k=2)
    )
    assert [result.file_id for result in results] == [10]
