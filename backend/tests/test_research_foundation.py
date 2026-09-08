from sqlalchemy.dialects.mysql import BIGINT

from app.db.base import Base


def test_research_tables_and_unsigned_bigint_primary_keys_are_registered() -> None:
    expected = {
        "research_resource",
        "research_analysis",
        "research_chat_session",
        "research_chat_message",
    }
    assert expected.issubset(Base.metadata.tables)
    assert "research_conversation" not in Base.metadata.tables
    assert "project_evidence_card" not in Base.metadata.tables
    for table_name in expected:
        primary_key = Base.metadata.tables[table_name].c.id
        assert isinstance(primary_key.type, BIGINT)
        assert primary_key.type.unsigned is True
        assert primary_key.autoincrement is True

    resource_columns = Base.metadata.tables["research_resource"].c
    assert "processing_status" in resource_columns
    assert "status" not in resource_columns

    analysis_columns = Base.metadata.tables["research_analysis"].c
    assert "field_sources_json" in analysis_columns
    assert "teacher_confirmed" in analysis_columns
    assert "teacher_confirmed_at" in analysis_columns

    evidence_columns = Base.metadata.tables["evidence_card"].c
    assert "card_status" in evidence_columns
    assert "review_status" not in evidence_columns
    assert "recommended_strategies_json" in evidence_columns
    assert "implementation_conditions_json" in evidence_columns
    assert "source_metadata_json" in evidence_columns
    assert "confirmed_by" in evidence_columns
    assert "confirmed_at" in evidence_columns
