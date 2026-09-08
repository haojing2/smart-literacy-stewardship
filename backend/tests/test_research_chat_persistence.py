from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.research_chat_service import ResearchChatService


class StubDatabase:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    @staticmethod
    def refresh(_message: object) -> None:
        pass


class StubProjectKnowledge:
    async def search(self, *, project_id: int, query: str, top_k: int):
        assert project_id == 9
        assert query == "What evidence is available?"
        assert top_k == 5
        return []


class StubRepository:
    def __init__(self) -> None:
        self.session = SimpleNamespace(
            id=4,
            project_id=9,
            resource_id=None,
            status="ACTIVE",
            conversation_summary=None,
        )
        self.project = SimpleNamespace(
            id=9,
            title="Project",
            topic="AI literacy",
            grade=5,
            class_hours=1,
        )
        self.messages: list[SimpleNamespace] = []

    def get_owned_session(self, **_kwargs):
        return self.session

    def get_owned_project(self, **_kwargs):
        return self.project

    def next_sequence_no(self, **_kwargs) -> int:
        return len(self.messages) + 1

    def create_message(self, *, session_id: int, role: str, sequence_no: int, content: str, metadata=None):
        message = SimpleNamespace(
            id=len(self.messages) + 1,
            session_id=session_id,
            role=role,
            sequence_no=sequence_no,
            content=content,
            metadata_json=metadata,
        )
        self.messages.append(message)
        return message

    @staticmethod
    def touch_session(_session) -> None:
        pass

    def list_messages(self, **_kwargs):
        return self.messages


class FailingStreamProvider:
    async def stream_chat(self, _request):
        yield "partial "
        raise RuntimeError("provider unavailable")


class SuccessfulStreamProvider:
    async def stream_chat(self, _request):
        yield "complete "
        yield "answer"


async def _consume(service: ResearchChatService) -> list[str]:
    chunks: list[str] = []
    async for chunk in service.stream_message(
        current_user_id=1,
        session_id=4,
        content="What evidence is available?",
    ):
        chunks.append(chunk)
    return chunks


def _service(provider: object) -> tuple[ResearchChatService, StubRepository]:
    service = ResearchChatService(
        StubDatabase(),  # type: ignore[arg-type]
        provider,  # type: ignore[arg-type]
        project_knowledge=StubProjectKnowledge(),  # type: ignore[arg-type]
    )
    repository = StubRepository()
    service.repository = repository  # type: ignore[assignment]
    return service, repository


def test_stream_failure_keeps_one_user_message_and_records_delivery_error() -> None:
    service, repository = _service(FailingStreamProvider())

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(_consume(service))

    assert [message.role for message in repository.messages] == ["USER"]
    user_message = repository.messages[0]
    assert user_message.session_id == 4
    assert user_message.metadata_json == {
        "conversationId": 4,
        "projectId": 9,
        "deliveryStatus": "FAILED",
        "error": "RuntimeError: provider unavailable",
    }


def test_stream_saves_one_complete_assistant_message_after_all_chunks() -> None:
    service, repository = _service(SuccessfulStreamProvider())

    assert asyncio.run(_consume(service)) == ["complete ", "answer"]

    assert [message.role for message in repository.messages] == ["USER", "ASSISTANT"]
    assert repository.messages[1].content == "complete answer"
    assert repository.messages[0].metadata_json["deliveryStatus"] == "COMPLETED"
    assert repository.messages[1].metadata_json == {
        "conversationId": 4,
        "projectId": 9,
        "deliveryStatus": "COMPLETED",
    }
