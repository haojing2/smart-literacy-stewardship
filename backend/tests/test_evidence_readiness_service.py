from __future__ import annotations

import asyncio

import pytest

from app.assistants.mock_research_assistant import MockResearchAssistant
from app.schemas.evidence import EvidenceSourceMetadata
from app.schemas.research_assistant import (
    EvidenceCardGenerationRequest,
    ResearchAnalysisResult,
)
from app.services.evidence_readiness_service import (
    EvidenceNotReadyError,
    EvidenceReadinessService,
)
from app.services.research_assistant_service import ResearchAssistantService


def source_metadata() -> EvidenceSourceMetadata:
    return EvidenceSourceMetadata(
        resource_id=101,
        original_filename="study.pdf",
        media_type="application/pdf",
        sha256="a" * 64,
    )


def analysis(**updates: object) -> ResearchAnalysisResult:
    values: dict[str, object] = {
        "research_subjects": [],
        "research_topics": [],
        "ai_literacy_dimensions": [],
        "teaching_strategies": [],
        "intervention_duration": None,
        "assessment_tools": [],
        "main_findings": [],
        "limitations": [],
        "source_excerpt": "source text",
    }
    values.update(updates)
    return ResearchAnalysisResult.model_validate(values)


def test_required_fields_control_status_independently_from_score() -> None:
    result = EvidenceReadinessService.evaluate(
        analysis(
            research_topics=["topic"],
            ai_literacy_dimensions=["critical evaluation"],
            teaching_strategies=["source comparison"],
            intervention_duration="8 weeks",
            assessment_tools=["rubric"],
            main_findings=["finding"],
            limitations=["limitation"],
        ),
        source_metadata(),
    )

    assert result.readiness_score == 85
    assert result.readiness_status == "INCOMPLETE"
    assert result.ready is False
    assert result.missing_required_fields == ["participants"]
    assert result.missing_recommended_fields == []


def test_all_required_fields_are_ready_even_without_recommended_fields() -> None:
    result = EvidenceReadinessService.evaluate(
        analysis(
            research_subjects=["participants"],
            teaching_strategies=["strategy"],
            main_findings=["finding"],
        ),
        source_metadata(),
    )

    assert result.readiness_score == 60
    assert result.readiness_status == "READY"
    assert result.ready is True
    assert result.missing_required_fields == []
    assert result.missing_recommended_fields == [
        "researchTopic",
        "aiLiteracyDimensions",
        "intervention",
        "assessmentTools",
        "limitations",
    ]


def test_source_metadata_is_a_required_business_field() -> None:
    result = EvidenceReadinessService.evaluate(
        analysis(
            research_subjects=["participants"],
            research_topics=["topic"],
            ai_literacy_dimensions=["dimension"],
            teaching_strategies=["strategy"],
            intervention_duration="8 weeks",
            assessment_tools=["rubric"],
            main_findings=["finding"],
            limitations=["limitation"],
        ),
        None,
    )

    assert result.readiness_score == 85
    assert result.readiness_status == "INCOMPLETE"
    assert result.missing_required_fields == ["sourceMetadata"]


def test_source_metadata_must_match_generation_resource() -> None:
    result = EvidenceReadinessService.evaluate(
        analysis(
            research_subjects=["participants"],
            teaching_strategies=["strategy"],
            main_findings=["finding"],
        ),
        source_metadata(),
        expected_resource_id=202,
    )

    assert result.readiness_status == "INCOMPLETE"
    assert result.missing_required_fields == ["sourceMetadata"]


def test_business_generation_facade_rejects_incomplete_analysis() -> None:
    request = EvidenceCardGenerationRequest(
        resource_id=101,
        source_file_name="study.pdf",
        analysis=analysis(
            research_topics=["topic"],
            ai_literacy_dimensions=["dimension"],
            teaching_strategies=["strategy"],
            intervention_duration="8 weeks",
            assessment_tools=["rubric"],
            main_findings=["finding"],
            limitations=["limitation"],
        ),
    )

    with pytest.raises(EvidenceNotReadyError) as error:
        asyncio.run(
            ResearchAssistantService(
                MockResearchAssistant()
            ).generate_evidence_card(
                request,
                source_metadata=source_metadata(),
            )
        )
    assert error.value.readiness.readiness_score == 85
    assert error.value.readiness.readiness_status == "INCOMPLETE"


def test_business_generation_facade_allows_all_required_fields() -> None:
    request = EvidenceCardGenerationRequest(
        resource_id=101,
        source_file_name="study.pdf",
        analysis=analysis(
            research_subjects=["participants"],
            teaching_strategies=["strategy"],
            main_findings=["finding"],
        ),
    )

    response = asyncio.run(
        ResearchAssistantService(MockResearchAssistant()).generate_evidence_card(
            request,
            source_metadata=source_metadata(),
        )
    )
    assert response.data.review_status == "DRAFT"
