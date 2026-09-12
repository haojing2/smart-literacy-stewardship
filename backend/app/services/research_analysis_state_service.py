from app.schemas.evidence import EvidenceSourceMetadata
from app.schemas.research_assistant import (
    ResearchAnalysisEditableView,
    ResearchAnalysisEditRequest,
    ResearchAnalysisPatch,
    ResearchAnalysisReadiness,
    ResearchAnalysisResult,
)
from app.services.evidence_readiness_service import EvidenceReadinessService


EDITABLE_FIELD_SOURCES = {
    "participants": "research_subjects",
    "researchTopics": "research_topics",
    "aiLiteracyDimensions": "ai_literacy_dimensions",
    "teachingStrategies": "teaching_strategies",
    "intervention": "intervention_duration",
    "assessmentTools": "assessment_tools",
    "mainFindings": "main_findings",
    "limitations": "limitations",
    "teachingImplications": "teaching_implications",
}


class ResearchAnalysisStateService:
    @staticmethod
    def readiness(
        analysis: ResearchAnalysisResult,
        source_metadata: EvidenceSourceMetadata | None,
    ) -> ResearchAnalysisReadiness:
        return EvidenceReadinessService.evaluate(
            analysis,
            source_metadata,
        )

    @classmethod
    def with_readiness(
        cls,
        analysis: ResearchAnalysisResult,
        source_metadata: EvidenceSourceMetadata | None,
    ) -> ResearchAnalysisResult:
        readiness = cls.readiness(analysis, source_metadata)
        return analysis.model_copy(
            update={"evidence_ready": readiness.readiness_status == "READY"}
        )

    @classmethod
    def apply_patch(
        cls,
        analysis: ResearchAnalysisResult,
        patch: ResearchAnalysisPatch | None,
        source_metadata: EvidenceSourceMetadata | None,
    ) -> ResearchAnalysisResult:
        if patch is None:
            return cls.with_readiness(analysis, source_metadata)
        updated = analysis.model_dump(mode="python", by_alias=False)
        updated.update(
            patch.model_dump(
                exclude_none=True,
                mode="python",
                by_alias=False,
            )
        )
        return cls.with_readiness(
            ResearchAnalysisResult.model_validate(updated),
            source_metadata,
        )

    @classmethod
    def from_edit_request(
        cls,
        request: ResearchAnalysisEditRequest,
        *,
        source_excerpt: str | None,
        source_metadata: EvidenceSourceMetadata | None,
    ) -> ResearchAnalysisResult:
        return cls.with_readiness(
            ResearchAnalysisResult(
                research_subjects=request.participants,
                research_topics=request.research_topics,
                ai_literacy_dimensions=request.ai_literacy_dimensions,
                teaching_strategies=request.teaching_strategies,
                intervention_duration=request.intervention,
                assessment_tools=request.assessment_tools,
                main_findings=request.main_findings,
                limitations=request.limitations,
                teaching_implications=request.teaching_implications,
                source_excerpt=source_excerpt,
            ),
            source_metadata,
        )

    @staticmethod
    def editable_view(
        analysis: ResearchAnalysisResult,
    ) -> ResearchAnalysisEditableView:
        return ResearchAnalysisEditableView(
            participants=analysis.research_subjects,
            research_topics=analysis.research_topics,
            ai_literacy_dimensions=analysis.ai_literacy_dimensions,
            teaching_strategies=analysis.teaching_strategies,
            intervention=analysis.intervention_duration,
            assessment_tools=analysis.assessment_tools,
            main_findings=analysis.main_findings,
            limitations=analysis.limitations,
            teaching_implications=analysis.teaching_implications,
        )

    @staticmethod
    def initial_mock_sources() -> dict[str, str]:
        return {field: "MOCK" for field in EDITABLE_FIELD_SOURCES}

    @staticmethod
    def teacher_sources() -> dict[str, str]:
        return {field: "TEACHER" for field in EDITABLE_FIELD_SOURCES}

    @staticmethod
    def confirmed_sources(
        current: dict[str, str] | None,
        analysis: ResearchAnalysisResult,
    ) -> dict[str, str]:
        sources = {
            **ResearchAnalysisStateService.initial_mock_sources(),
            **(current or {}),
        }
        for api_field, internal_field in EDITABLE_FIELD_SOURCES.items():
            value = getattr(analysis, internal_field)
            if (isinstance(value, list) and value) or (isinstance(value, str) and value.strip()):
                sources[api_field] = "TEACHER"
        return sources

    @staticmethod
    def sources_after_patch(
        current: dict[str, str] | None,
        patch: ResearchAnalysisPatch,
        *,
        source: str = "AI_CHAT",
    ) -> dict[str, str]:
        sources = {
            **ResearchAnalysisStateService.initial_mock_sources(),
            **(current or {}),
        }
        changed_internal_fields = patch.model_dump(
            exclude_none=True,
            by_alias=False,
        ).keys()
        for api_field, internal_field in EDITABLE_FIELD_SOURCES.items():
            if internal_field in changed_internal_fields:
                sources[api_field] = source
        return sources
