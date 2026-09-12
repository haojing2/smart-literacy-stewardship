from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from app.assistants.base import ResearchAssistantProvider
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
    failed_batches: list[str]


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
        probe = getattr(self.provider, "probe_research_analysis_model", None)
        if callable(probe):
            await probe(project_id=project_id, resource_id=resource_id)
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
                    analysis_batch=batch_name,
                    top_k=2,
                    max_chunks=4,
                    max_chars=4500,
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
                        retrieved_candidates=evidence.retrieved_count,
                        selected_chunks=[
                            source.chunk_id for source in evidence.unique_sources
                        ],
                        context_chars=evidence.context_chars,
                        missing_fields=fields,
                        analysis_evidence=evidence.prompt_context,
                        current_analysis=empty,
                    )
                )
                return batch_name, evidence, response.data, response.provider

        batch_results = await asyncio.gather(*(
            extract_batch(batch_name, fields)
            for batch_name, fields in ANALYSIS_BATCHES.items()
        ), return_exceptions=True)
        batches = []
        failed_batches: list[str] = []
        for batch_name, result in zip(ANALYSIS_BATCHES, batch_results, strict=True):
            if isinstance(result, BaseException):
                failed_batches.append(batch_name)
                logger.warning(
                    "Research analysis batch failed project_id=%s resource_id=%s "
                    "analysis_batch=%s batch_status=FAILED failure_type=%s",
                    project_id,
                    resource_id,
                    batch_name,
                    type(result).__name__,
                )
            else:
                batches.append(result)
        if not batches:
            raise RuntimeError("All research analysis batches failed")
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

        first_pass = ResearchAnalysisResult.model_validate(merged)
        first_pass_evidence = ResearchAnalysisEvidenceBundle(
            prompt_context="\n\n".join(context_parts),
            field_sources=field_sources,
            unique_sources=list(unique_sources.values()),
            retrieved_count=retrieved_count,
            context_chars=sum(batch.context_chars for _, batch, _, _ in batches),
        )
        first_missing = self._missing_fields(
            first_pass, first_pass_evidence, require_evidence=False
        )

        field_batches = {
            field: batch_name
            for batch_name, fields in ANALYSIS_BATCHES.items()
            for field in fields
        }

        async def supplement_field(
            field: str,
        ) -> tuple[str, ResearchAnalysisEvidenceBundle, ResearchAnalysisPatch, str]:
            batch_name = field_batches[field]
            async with semaphore:
                field_evidence = await self.evidence_collector.collect(
                    project_id=project_id,
                    file_id=resource_id,
                    fields=[field],
                    analysis_batch=batch_name,
                    top_k=2,
                    max_chunks=2,
                    max_chars=2500,
                )
                logger.info(
                    "Research analysis field supplement prepared project_id=%s "
                    "resource_id=%s analysis_batch=%s field=%s "
                    "retrieved_candidates=%s selected_chunks=%s context_chars=%s",
                    project_id,
                    resource_id,
                    batch_name,
                    field,
                    field_evidence.retrieved_count,
                    [source.chunk_id for source in field_evidence.unique_sources],
                    field_evidence.context_chars,
                )
                response = await self.provider.supplement_research_analysis(
                    ResearchAnalysisSupplementRequest(
                        project_id=project_id,
                        resource_id=resource_id,
                        analysis_batch=batch_name,
                        analysis_field=field,
                        retrieved_chunks=len(field_evidence.unique_sources),
                        retrieved_candidates=field_evidence.retrieved_count,
                        selected_chunks=[
                            source.chunk_id for source in field_evidence.unique_sources
                        ],
                        context_chars=field_evidence.context_chars,
                        missing_fields=[field],
                        analysis_evidence=field_evidence.prompt_context,
                        current_analysis=first_pass,
                    )
                )
                return field, field_evidence, response.data, response.provider

        supplement_results = await asyncio.gather(
            *(supplement_field(field) for field in first_missing),
            return_exceptions=True,
        )
        successful_supplements = []
        for field, result in zip(first_missing, supplement_results, strict=True):
            if isinstance(result, BaseException):
                failed_batches.append(f"{field_batches[field]}:{field}")
                logger.warning(
                    "Research analysis field supplement failed project_id=%s "
                    "resource_id=%s analysis_batch=%s field=%s batch_status=FAILED "
                    "failure_type=%s",
                    project_id,
                    resource_id,
                    field_batches[field],
                    field,
                    type(result).__name__,
                )
            else:
                successful_supplements.append(result)

        for field, field_evidence, patch, provider_name in successful_supplements:
            context_parts.append(
                f"[ANALYSIS FIELD {field}]\n{field_evidence.prompt_context}"
            )
            retrieved_count += field_evidence.retrieved_count
            field_sources[field] = field_evidence.field_sources.get(field, [])
            for source in field_evidence.unique_sources:
                unique_sources.setdefault(source.chunk_id, source)
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
            context_chars=sum(len(part) for part in context_parts),
        )
        final_missing = self._missing_fields(final, evidence, require_evidence=False)
        diagnostics = ResearchAnalysisDiagnostics(
            retrieved_field_coverage=evidence.field_coverage,
            first_pass_fields=self._non_empty_count(first_pass),
            missing_fields_after_first_pass=first_missing,
            supplement_attempted=bool(first_missing),
            supplement_failed=bool(failed_batches),
            final_fields=self._non_empty_count(final),
            missing_fields_after_supplement=final_missing,
            provider=provider_name,
            failed_batches=failed_batches,
        )
        logger.info(
            "Research structured analysis project_id=%s resource_id=%s analysis_provider=%s "
            "analysis_generation_status=READY first_pass_non_empty_fields=%s "
            "missing_fields_after_first_pass=%s supplement_attempted=%s supplement_failed=%s "
            "missing_fields_after_supplement=%s failed_batches=%s",
            project_id,
            resource_id,
            diagnostics.provider,
            diagnostics.first_pass_fields,
            diagnostics.missing_fields_after_first_pass,
            diagnostics.supplement_attempted,
            diagnostics.supplement_failed,
            diagnostics.missing_fields_after_supplement,
            diagnostics.failed_batches,
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
