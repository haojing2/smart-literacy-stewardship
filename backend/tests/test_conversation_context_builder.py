from types import SimpleNamespace

from app.agents.research.context_builder import ConversationContextBuilder
from app.schemas.research_assistant import ResearchChatMessageInput


def test_conversation_context_builder_uses_summary_and_only_recent_valid_turns() -> None:
    conversation = SimpleNamespace(conversation_summary="Teacher is planning grade five lessons.")
    history = [
        ResearchChatMessageInput(role="SYSTEM", content="Page loaded")
    ] + [
        ResearchChatMessageInput(
            role="USER" if index % 2 == 0 else "ASSISTANT",
            content=f"turn-{index}",
        )
        for index in range(12)
    ] + [ResearchChatMessageInput(role="USER", content="current question")]

    messages = ConversationContextBuilder.build(
        conversation=conversation,  # type: ignore[arg-type]
        messages=history,
        current_question="current question",
    )

    assert messages[0] == {
        "role": "system",
        "content": "Earlier conversation summary:\nTeacher is planning grade five lessons.",
    }
    assert len(messages) == 12  # summary + 10 history turns + current question
    assert messages[-1] == {"role": "user", "content": "current question"}
    assert sum(item["content"] == "current question" for item in messages) == 1
    assert all(item["role"] in {"system", "user", "assistant"} for item in messages)
    assert all(item["content"] != "Page loaded" for item in messages)


def test_conversation_context_builder_keeps_current_question_once_when_not_persisted() -> None:
    messages = ConversationContextBuilder.build(
        conversation=SimpleNamespace(conversation_summary=None),  # type: ignore[arg-type]
        messages=[ResearchChatMessageInput(role="ASSISTANT", content="How can I help?")],
        current_question="Tell me about cooperative learning",
    )

    assert messages == [
        {"role": "assistant", "content": "How can I help?"},
        {"role": "user", "content": "Tell me about cooperative learning"},
    ]
