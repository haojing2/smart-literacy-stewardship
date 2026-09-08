import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services.project_knowledge_service import ProjectKnowledgeSource
from app.tools.research.search_project_documents import SearchProjectDocumentsTool


class StubProjectKnowledge:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    async def search(self, *, project_id: int, query: str, top_k: int = 5):
        self.calls.append((project_id, query))
        return [
            ProjectKnowledgeSource(
                content="retrieved chunk",
                filename="paper.pdf",
                file_id=8,
                chunk_id="chunk-1",
                chunk_index=0,
                score=0.91,
            )
        ]


class StubRepository:
    def __init__(self, session) -> None:
        self.session = session

    def get_owned_session(self, *, session_id: int, user_id: int):
        assert session_id == 4
        assert user_id == 2
        return self.session


def test_document_search_tool_uses_only_the_current_session_project() -> None:
    knowledge = StubProjectKnowledge()
    tool = SearchProjectDocumentsTool(
        None,  # type: ignore[arg-type]
        current_user_id=2,
        session_id=4,
        project_knowledge=knowledge,  # type: ignore[arg-type]
    )
    tool._repository = StubRepository(SimpleNamespace(project_id=77))  # type: ignore[assignment]

    result = asyncio.run(tool.execute({"query": "cooperative learning"}))

    assert knowledge.calls == [(77, "cooperative learning")]
    assert result[0].content == "retrieved chunk"
    assert result[0].filename == "paper.pdf"
    assert result[0].file_id == 8
    assert result[0].chunk_id == "chunk-1"
    assert result[0].score == 0.91


def test_document_search_tool_rejects_model_supplied_project_id() -> None:
    tool = SearchProjectDocumentsTool(
        None,  # type: ignore[arg-type]
        current_user_id=2,
        session_id=4,
        project_knowledge=StubProjectKnowledge(),  # type: ignore[arg-type]
    )

    with pytest.raises(ValidationError):
        asyncio.run(tool.execute({"query": "anything", "project_id": 999}))
