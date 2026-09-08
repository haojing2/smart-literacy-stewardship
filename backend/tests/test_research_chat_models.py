from app.models.research import ResearchChatMessage, ResearchChatSession
from app.schemas.research_assistant import ResearchChatMessageResponse


def test_research_conversation_and_message_models_expose_required_fields() -> None:
    session_columns = set(ResearchChatSession.__table__.columns.keys())
    message_columns = set(ResearchChatMessage.__table__.columns.keys())

    assert {"id", "project_id", "user_id", "title", "conversation_summary"} <= session_columns
    assert {"id", "session_id", "role", "content", "metadata_json", "created_at"} <= message_columns


def test_message_metadata_is_exposed_using_the_stable_api_field_name() -> None:
    response = ResearchChatMessageResponse(
        message_id=1,
        role="ASSISTANT",
        sequence_no=2,
        content="Research support",
        metadata={"source": "knowledge_base"},
        created_at="2026-09-08T00:00:00",
    )

    assert response.model_dump(by_alias=True)["metadata"] == {"source": "knowledge_base"}
