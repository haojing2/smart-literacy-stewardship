from __future__ import annotations

from dataclasses import dataclass
import logging

from app.assistants.base import ResearchAssistantProvider
from app.schemas.research_assistant import (
    ResearchAnalysisPatch,
    ResearchAnalysisRequest,
    ResearchAnalysisResult,
    ResearchAnalysisSupplementRequest,
)
from app.services.research_analysis_evidence_service import (
    ResearchAnalysisEvidenceBundle,
    ResearchAnalysisEvidenceCollector,
)


logger = logging.getLogger(__name__)


FIELD_ATTRIBUTES = {
    "participants": "research_subjects",
    "researchTopic": "research_topics",
    "aiLiteracyDimensions": "ai_literacy_dimensions",
    "teachingStrategies": "teaching_strategies",
    "intervention": "intervention_duration",
    "assessmentTools": "assessment_tools",
    "mainFindings": "main_findings",
    "limitations": "limitations",
    "teachingImplications": "teaching_implications",
}


@dataclass(frozen=True)
class ResearchAnalysisDiagnostics:
    retrieved_field_coverage: dict[str, int]
    first_pass_fields: int
    missing_fields_after_first_pass: list[str]
    supplement_attempted: bool
    supplement_failed: bool
    final_fields: int
    missing_fields_after_supplement: list[str]
    provider: str


@dataclass(frozen=True)
class ResearchAnalysisExtractionResult:
    analysis: ResearchAnalysisResult
    evidence: ResearchAnalysisEvidenceBundle
    diagnostics: ResearchAnalysisDiagnostics
    generation_status: str = "READY"


class ResearchAnalysisExtractionService:
    """Strict PDF ETL through the general structured-assistant provider."""

    def __init__(
        self,
        provider: ResearchAssistantProvider,
        evidence_collector: ResearchAnalysisEvidenceCollector,
    ) -> None:
        self.provider = provider
        self.evidence_collector = evidence_collector

    async def extract(
        self,
        *,
        project_id: int,
        resource_id: int,
        project_title: str | None,
        project_topic: str | None,
    ) -> ResearchAnalysisExtractionResult:
        evidence = await self.evidence_collector.collect(
            project_id=project_id, file_id=resource_id
        )
        first_response = await self.provider.analyze_research(
            ResearchAnalysisRequest(
                resource_id=resource_id,
                analysis_evidence=evidence.prompt_context,
                project_title=project_title,
                project_topic=project_topic,
            )
        )
        first = first_response.data
        missing = self._missing_fields(first, evidence)
        supplement_attempted = bool(missing)
        supplement_failed = False
        final = first
        if supplement_attempted:
            try:
                supplement_evidence = await self.evidence_collector.collect(
                    project_id=project_id,
                    file_id=resource_id,
                    fields=missing,
                )
                supplement_response = await self.provider.supplement_research_analysis(
                    ResearchAnalysisSupplementRequest(
                        resource_id=resource_id,
                        missing_fields=missing,
                        analysis_evidence=supplement_evidence.prompt_context,
                        current_analysis=first,
                    )
                )
                final = self._merge_missing(first, supplement_response.data, missing)
            except Exception as exc:
                supplement_failed = True
                final = first
                logger.warning(
                    "Research analysis supplement degraded resource_id=%s "
                    "missing_fields=%s failure_type=%s fallback=FIRST_PASS_RESULT "
                    "analysis_generation_status=READY",
                    resource_id,
                    missing,
                    type(exc).__name__,
                )

        final_missing = self._missing_fields(final, evidence, require_evidence=False)
        diagnostics = ResearchAnalysisDiagnostics(
            retrieved_field_coverage=evidence.field_coverage,
            first_pass_fields=self._non_empty_count(first),
            missing_fields_after_first_pass=missing,
            supplement_attempted=supplement_attempted,
            supplement_failed=supplement_failed,
            final_fields=self._non_empty_count(final),
            missing_fields_after_supplement=final_missing,
            provider=first_response.provider,
        )
        logger.info(
            "Research structured analysis project_id=%s resource_id=%s analysis_provider=%s "
            "analysis_generation_status=READY first_pass_non_empty_fields=%s "
            "missing_fields_after_first_pass=%s supplement_attempted=%s supplement_failed=%s "
            "missing_fields_after_supplement=%s",
            project_id,
            resource_id,
            diagnostics.provider,
            diagnostics.first_pass_fields,
            diagnostics.missing_fields_after_first_pass,
            diagnostics.supplement_attempted,
            diagnostics.supplement_failed,
            diagnostics.missing_fields_after_supplement,
        )
        return ResearchAnalysisExtractionResult(final, evidence, diagnostics)

    @classmethod
    def _missing_fields(
        cls,
        analysis: ResearchAnalysisResult,
        evidence: ResearchAnalysisEvidenceBundle,
        *,
        require_evidence: bool = True,
    ) -> list[str]:
        return [
            field
            for field, attribute in FIELD_ATTRIBUTES.items()
            if (not require_evidence or evidence.field_sources.get(field))
            and not cls._has_value(getattr(analysis, attribute))
        ]

    @classmethod
    def _non_empty_count(cls, analysis: ResearchAnalysisResult) -> int:
        return sum(
            cls._has_value(getattr(analysis, attribute))
            for attribute in FIELD_ATTRIBUTES.values()
        )

    @staticmethod
    def _has_value(value: object) -> bool:
        if isinstance(value, list):
            return any(isinstance(item, str) and item.strip() for item in value)
        return isinstance(value, str) and bool(value.strip())

    @classmethod
    def _merge_missing(
        cls,
        first: ResearchAnalysisResult,
        supplement: ResearchAnalysisPatch,
        missing: list[str],
    ) -> ResearchAnalysisResult:
        merged = first.model_dump(mode="python", by_alias=False)
        for field in missing:
            attribute = FIELD_ATTRIBUTES[field]
            value = getattr(supplement, attribute)
            if cls._has_value(value):
                merged[attribute] = value
        return ResearchAnalysisResult.model_validate(merged)
