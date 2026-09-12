from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from app.assistants.base import ResearchAssistantProvider
from app.core.config import settings
from app.schemas.research_assistant import (
    ResearchAnalysisPatch,
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

ANALYSIS_BATCHES: dict[str, list[str]] = {
    "A": ["participants", "researchTopic", "intervention"],
    "B": ["aiLiteracyDimensions", "teachingStrategies", "assessmentTools"],
    "C": ["mainFindings", "limitations", "teachingImplications"],
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
        semaphore = asyncio.Semaphore(2)
        empty = ResearchAnalysisResult()

        async def extract_batch(
            batch_name: str, fields: list[str]
        ) -> tuple[str, ResearchAnalysisEvidenceBundle, ResearchAnalysisPatch, str]:
            async with semaphore:
                evidence = await self.evidence_collector.collect(
                    project_id=project_id,
                    file_id=resource_id,
                    fields=fields,
                    top_k=2,
                    max_chunks=min(settings.research_analysis_max_chunks, 6),
                    max_chars=min(settings.research_analysis_max_context_chars, 10_000),
                )
                logger.info(
                    "Research analysis batch prepared project_id=%s resource_id=%s "
                    "analysis_batch=%s retrieved_chunks=%s context_chars=%s",
                    project_id,
                    resource_id,
                    batch_name,
                    len(evidence.unique_sources),
                    evidence.context_chars,
                )
                response = await self.provider.supplement_research_analysis(
                    ResearchAnalysisSupplementRequest(
                        project_id=project_id,
                        resource_id=resource_id,
                        analysis_batch=batch_name,
                        retrieved_chunks=len(evidence.unique_sources),
                        context_chars=evidence.context_chars,
                        missing_fields=fields,
                        analysis_evidence=evidence.prompt_context,
                        current_analysis=empty,
                    )
                )
                return batch_name, evidence, response.data, response.provider

        batches = await asyncio.gather(*(
            extract_batch(batch_name, fields)
            for batch_name, fields in ANALYSIS_BATCHES.items()
        ))
        merged: dict[str, object] = empty.model_dump(mode="python", by_alias=False)
        field_sources: dict[str, list] = {}
        unique_sources = {}
        retrieved_count = 0
        context_parts: list[str] = []
        provider_name = "unknown"
        for batch_name, batch_evidence, patch, provider_name in batches:
            context_parts.append(f"[ANALYSIS BATCH {batch_name}]\n{batch_evidence.prompt_context}")
            retrieved_count += batch_evidence.retrieved_count
            field_sources.update(batch_evidence.field_sources)
            for source in batch_evidence.unique_sources:
                unique_sources.setdefault(source.chunk_id, source)
            for field in ANALYSIS_BATCHES[batch_name]:
                attribute = FIELD_ATTRIBUTES[field]
                value = getattr(patch, attribute)
                if self._has_value(value):
                    merged[attribute] = value

        final = ResearchAnalysisResult.model_validate(merged)
        evidence = ResearchAnalysisEvidenceBundle(
            prompt_context="\n\n".join(context_parts),
            field_sources=field_sources,
            unique_sources=list(unique_sources.values()),
            retrieved_count=retrieved_count,
            context_chars=sum(batch.context_chars for _, batch, _, _ in batches),
        )
        final_missing = self._missing_fields(final, evidence, require_evidence=False)
        diagnostics = ResearchAnalysisDiagnostics(
            retrieved_field_coverage=evidence.field_coverage,
            first_pass_fields=self._non_empty_count(final),
            missing_fields_after_first_pass=final_missing,
            supplement_attempted=False,
            supplement_failed=False,
            final_fields=self._non_empty_count(final),
            missing_fields_after_supplement=final_missing,
            provider=provider_name,
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
            False,
            False,
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
