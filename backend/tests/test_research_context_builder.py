import asyncio
from types import SimpleNamespace

from app.agents.research.context_builder import ResearchConversationContextBuilder
from app.schemas.research_assistant import (
    ResearchChatMessageInput,
    ResearchConversationSummaryResponse,
    ResearchConversationSummaryResult,
)
from app.services.project_knowledge_service import ProjectKnowledgeSource
from app.services.research_chat_service import ResearchChatService


def test_context_builder_bounds_recent_history_and_excludes_system_messages() -> None:
    project = SimpleNamespace(
        title="Collaborative learning",
        topic="AI literacy",
        grade=5,
        class_hours=2,
        student_level=None,
        student_experience="Basic inquiry experience",
        lesson_minutes=40,
        class_size=36,
        constraints_json=["tablets shared in pairs"],
        context_diagnosis_json={"coreProblem": "evaluate AI information"},
    )
    history = [
        ResearchChatMessageInput(role="USER", content=f"turn-{index}")
        for index in range(12)
    ]
    history.append(ResearchChatMessageInput(role="SYSTEM", content="do not include"))

    recent = ResearchConversationContextBuilder.recent_messages(history)
    context = ResearchConversationContextBuilder.build(
        project=project,
        conversation_summary="Teacher wants cooperative learning evidence.",
        recent_messages=recent,
        current_question="Why is it suitable for grade five?",
    )

    assert len(recent) == 10
    assert "turn-0" not in context
    assert "turn-2" in context
    assert "do not include" not in context
    assert "[CURRENT PROJECT]" in context
    assert "[EARLIER CONVERSATION SUMMARY]" in context
    assert "[RECENT CONVERSATION]" in context
    assert "[CURRENT QUESTION]" in context


def test_summary_starts_only_after_twenty_effective_messages() -> None:
    session = SimpleNamespace(
        id=7,
        conversation_summary=None,
        conversation_summary_through_sequence_no=0,
    )
    messages = [
        SimpleNamespace(
            sequence_no=index,
            role="USER" if index % 2 else "ASSISTANT",
            content=f"turn-{index}",
        )
        for index in range(1, 21)
    ]

    class Repository:
        def get_owned_session(self, **_kwargs):
            return session

        def list_messages(self, **_kwargs):
            return messages

        def update_conversation_summary(self, _session, *, summary, through_sequence_no):
            session.conversation_summary = summary
            session.conversation_summary_through_sequence_no = through_sequence_no

    class Database:
        def commit(self):
            pass

        def rollback(self):
            pass

    class Provider:
        def __init__(self):
            self.requests = []

        async def summarize_conversation(self, request):
            self.requests.append(request)
            return ResearchConversationSummaryResponse(
                provider="test",
                request_fingerprint="0" * 64,
                data=ResearchConversationSummaryResult(summary="compressed"),
            )

    provider = Provider()
    service = ResearchChatService(Database(), provider)  # type: ignore[arg-type]
    service.repository = Repository()  # type: ignore[assignment]

    # Exactly twenty effective messages stay verbatim and do not invoke the
    # provider. The next message is the first rolling-summary trigger.
    asyncio.run(service._update_conversation_summary(current_user_id=1, session_id=7))
    assert provider.requests == []

    messages.append(SimpleNamespace(sequence_no=21, role="USER", content="turn-21"))
    asyncio.run(service._update_conversation_summary(current_user_id=1, session_id=7))
    assert [item.content for item in provider.requests[0].messages] == [
        f"turn-{index}" for index in range(1, 12)
    ]
    assert session.conversation_summary_through_sequence_no == 11

    messages.extend(
        [
            SimpleNamespace(sequence_no=22, role="ASSISTANT", content="turn-22"),
            SimpleNamespace(sequence_no=23, role="USER", content="turn-23"),
        ]
    )
    asyncio.run(service._update_conversation_summary(current_user_id=1, session_id=7))
    assert [item.content for item in provider.requests[1].messages] == [
        "turn-12",
        "turn-13",
    ]
    assert session.conversation_summary_through_sequence_no == 13


def test_chat_request_reuses_persisted_summary_after_a_session_reload() -> None:
    project = SimpleNamespace(
        id=2,
        title="Cooperative learning project",
        topic="AI literacy",
        grade=5,
        class_hours=2,
        student_level=None,
        student_experience=None,
        lesson_minutes=None,
        class_size=None,
        constraints_json=None,
        context_diagnosis_json=None,
    )
    session = SimpleNamespace(
        id=9,
        project_id=2,
        resource_id=None,
        conversation_summary="The teacher is evaluating cooperative learning for grade five.",
    )
    messages = [
        SimpleNamespace(
            role="USER" if index % 2 else "ASSISTANT",
            content=f"turn-{index}",
        )
        for index in range(1, 13)
    ]

    class Repository:
        def get_owned_project(self, **_kwargs):
            return project

        def list_messages(self, **_kwargs):
            return messages

    class ProjectKnowledge:
        def __init__(self) -> None:
            self.calls: list[tuple[int, str, int]] = []

        async def search(self, *, project_id: int, query: str, top_k: int):
            self.calls.append((project_id, query, top_k))
            return [
                ProjectKnowledgeSource(
                    content=f"evidence-{index}",
                    filename="paper.pdf",
                    file_id=5,
                    chunk_id=f"chunk-{index}",
                    chunk_index=index,
                    score=0.1,
                )
                for index in range(6)
            ]

    project_knowledge = ProjectKnowledge()
    service = ResearchChatService(
        SimpleNamespace(), SimpleNamespace(), project_knowledge=project_knowledge  # type: ignore[arg-type]
    )
    service.repository = Repository()  # type: ignore[assignment]
    request = asyncio.run(
        service._chat_request(
            current_user_id=1,
            session=session,
            content="Why?",
            analysis=None,
        )
    )

    assert request.conversation_summary == session.conversation_summary
    assert len(request.history) == 10
    assert project_knowledge.calls == []
    assert request.project_knowledge_sources == []
    assert "USER: turn-1\n" not in request.conversation_context
    assert "USER: turn-3\n" in request.conversation_context
    assert "[CONVERSATION HISTORY]" in request.conversation_context
    assert "[PROJECT KNOWLEDGE EVIDENCE]" in request.conversation_context
    assert "No ready project knowledge sources were retrieved." in request.conversation_context
