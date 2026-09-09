from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.agents.research.errors import ResearchAgentContractError
from app.agents.research.spark_research_agent import SparkResearchAgent
from app.core.config import settings
from app.schemas.research_assistant import ResearchAnalysisRequest, ResearchAnalysisResult
from app.services.bm25_store_service import BM25StoreService
from app.services.chunk_service import MarkdownChunk
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.knowledge_base_path_service import KnowledgeBasePathService
from app.services.project_knowledge_service import ProjectKnowledgeService, ProjectKnowledgeSource
from app.services.research_chat_service import (
    ResearchChatService,
    ResearchKnowledgeIndexNotReadyError,
    ResearchRetrievalScopeError,
)
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


class SuccessfulProvider:
    async def analyze_research(self, request):
        return SimpleNamespace(
            provider="test",
            data=ResearchAnalysisResult(research_topics=["topic"]),
        )


class SessionRepository:
    def __init__(self) -> None:
        self.analysis_data = None
        self.analysis_generation_status = None

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
        self.analysis_generation_status = kwargs.get("generation_status")
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
    assert repository.analysis_generation_status == "FAILED"
    assert db.commits == 1


def test_successful_structured_analysis_is_saved_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.research_chat_service.EvidenceCardDraftService.generate_draft_if_ready_transition",
        lambda *args, **kwargs: None,
    )
    db = StubDb()
    repository = SessionRepository()
    service = ResearchChatService(db, SuccessfulProvider(), OneSourceKnowledge())  # type: ignore[arg-type]
    service.repository = repository  # type: ignore[assignment]
    service.get_session = lambda **kwargs: SimpleNamespace(session_id=51)  # type: ignore[method-assign]
    asyncio.run(service.create_session(
        current_user_id=1, project_id=1020,
        request=SimpleNamespace(resource_id=16, title=None),
    ))
    assert repository.analysis_generation_status == "READY"
    assert repository.analysis_data["research_topics"] == ["topic"]


def test_failed_analysis_retry_does_not_create_another_failed_version() -> None:
    existing = SimpleNamespace(id=40, version=1, generation_status="FAILED")

    class RetryRepository(SessionRepository):
        def __init__(self):
            super().__init__()
            self.marked_failed = 0

        def get_latest_analysis(self, **kwargs):
            return existing

        def mark_analysis_generation_failed(self, analysis, **kwargs):
            self.marked_failed += 1

    repository = RetryRepository()
    service = ResearchChatService(StubDb(), FailingProvider(), OneSourceKnowledge())  # type: ignore[arg-type]
    service.repository = repository  # type: ignore[assignment]
    service.get_session = lambda **kwargs: SimpleNamespace(session_id=51)  # type: ignore[method-assign]
    asyncio.run(service.create_session(
        current_user_id=1, project_id=1020,
        request=SimpleNamespace(resource_id=16, title=None),
    ))
    assert repository.marked_failed == 1
    assert repository.analysis_data is None


def test_failed_analysis_retry_success_creates_next_ready_version(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.research_chat_service.EvidenceCardDraftService.generate_draft_if_ready_transition",
        lambda *args, **kwargs: None,
    )
    existing = SimpleNamespace(id=40, version=1, generation_status="FAILED")

    class RetryRepository(SessionRepository):
        def __init__(self):
            super().__init__()
            self.analysis_version = None

        def get_latest_analysis(self, **kwargs):
            return existing

        def create_analysis(self, **kwargs):
            self.analysis_version = kwargs["version"]
            return super().create_analysis(**kwargs)

    repository = RetryRepository()
    service = ResearchChatService(StubDb(), SuccessfulProvider(), OneSourceKnowledge())  # type: ignore[arg-type]
    service.repository = repository  # type: ignore[assignment]
    service.get_session = lambda **kwargs: SimpleNamespace(session_id=51)  # type: ignore[method-assign]
    asyncio.run(service.create_session(
        current_user_id=1, project_id=1020,
        request=SimpleNamespace(resource_id=16, title=None),
    ))
    assert repository.analysis_version == 2
    assert repository.analysis_generation_status == "READY"


def test_resource_session_rejects_non_ready_index_before_analysis() -> None:
    repository = SessionRepository()
    resource = repository.get_owned_project_resource()
    resource.index_status = "indexing"
    repository.get_owned_project_resource = lambda **kwargs: resource
    service = ResearchChatService(StubDb(), FailingProvider(), OneSourceKnowledge())  # type: ignore[arg-type]
    service.repository = repository  # type: ignore[assignment]
    with pytest.raises(ResearchKnowledgeIndexNotReadyError) as caught:
        asyncio.run(service.create_session(
            current_user_id=1, project_id=1020,
            request=SimpleNamespace(resource_id=16, title=None),
        ))
    assert caught.value.index_status == "indexing"


def test_resource_chat_uses_single_file_retrieval_and_records_provenance() -> None:
    calls = []

    class Knowledge:
        async def search_resource(self, **kwargs):
            calls.append(kwargs)
            return [ProjectKnowledgeSource(
                content="paper evidence", project_id=1020, filename="paper.pdf",
                file_id=16, chunk_id="chunk-16", chunk_index=2, score=0.91,
            )]

        async def search(self, **kwargs):
            raise AssertionError("project search must not run for a resource session")

    class Repository:
        def get_owned_project(self, **kwargs):
            return SimpleNamespace(
                title="Project", topic="Topic", grade=7, class_hours=2,
                student_level="mixed", student_experience="beginner", class_size=36,
                lesson_minutes=45, ai_access_mode="shared", devices_json=["tablet"],
                constraints_json=["no phones"], additional_requirements="group work",
                context_diagnosis_json={"risk": "access"},
            )

        def list_messages(self, **kwargs):
            return []

    service = ResearchChatService(StubDb(), FailingProvider(), Knowledge())  # type: ignore[arg-type]
    service.repository = Repository()  # type: ignore[assignment]
    session = SimpleNamespace(
        id=51, project_id=1020, resource_id=16, conversation_summary=None,
    )
    request = asyncio.run(service._chat_request(
        current_user_id=1, session=session, content="What did this paper find?", analysis=None,
    ))
    assert calls[0]["file_id"] == 16
    assert request.retrieval_scope == "RESOURCE"
    assert request.student_experience == "beginner"
    metadata = service._assistant_message_metadata(session, request)
    assert metadata["retrievalScope"] == "RESOURCE"
    assert metadata["resourceId"] == 16
    assert metadata["retrievedSources"] == [{
        "fileId": 16, "filename": "paper.pdf", "chunkId": "chunk-16",
        "chunkIndex": 2, "score": 0.91,
    }]


def test_resource_chat_fails_loudly_on_cross_paper_source() -> None:
    class WrongKnowledge:
        async def search_resource(self, **kwargs):
            return [ProjectKnowledgeSource(
                content="wrong", project_id=1020, filename="other.pdf",
                file_id=17, chunk_id="chunk-17", chunk_index=0, score=1.0,
            )]

    class Repository:
        def get_owned_project(self, **kwargs):
            return SimpleNamespace(
                title="P", topic="T", grade=None, class_hours=None,
                student_level=None, student_experience=None, class_size=None,
                lesson_minutes=None, ai_access_mode=None, devices_json=None,
                constraints_json=None, additional_requirements=None,
                context_diagnosis_json=None,
            )

        def list_messages(self, **kwargs):
            return []

    service = ResearchChatService(StubDb(), FailingProvider(), WrongKnowledge())  # type: ignore[arg-type]
    service.repository = Repository()  # type: ignore[assignment]
    with pytest.raises(ResearchRetrievalScopeError):
        asyncio.run(service._chat_request(
            current_user_id=1,
            session=SimpleNamespace(id=51, project_id=1020, resource_id=16, conversation_summary=None),
            content="question", analysis=None,
        ))


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
