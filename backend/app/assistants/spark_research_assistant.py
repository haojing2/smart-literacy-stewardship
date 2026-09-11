"""Spark-backed implementation of the existing assistant provider contract."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

from app.assistants.base import ResearchAssistantProvider
from app.assistants.spark_client import (
    SparkContractError, SparkLLMClient, SparkOutputLengthError, SparkResponseParseError,
)
from app.core.config import settings
from app.assistants.prompts.course_assessment import build_course_assessment_messages
from app.assistants.prompts.course_blueprint import build_course_activity_regeneration_messages, build_course_blueprint_messages
from app.assistants.prompts.course_context import build_course_context_messages
from app.assistants.prompts.course_objective import build_course_objective_messages
from app.assistants.prompts.course_pedagogy import build_course_pedagogy_messages
from app.assistants.prompts.course_quality import build_course_quality_messages
from app.assistants.prompts.research import build_evidence_card_messages, build_research_analysis_messages, build_research_analysis_supplement_messages, build_research_chat_messages, build_research_chat_stream_messages
from app.assistants.prompts.resource_creation import (
    RESOURCE_OUTPUT_TEMPLATES,
    TEACHING_RESOURCE_STRUCTURE_RULES,
    build_teaching_resource_messages,
    normalize_assessment_content,
    validate_generated_resource,
)
from app.schemas.course_design import (
    CourseActivityProposal, CourseActivityRegenerationRequest, CourseAssessmentGenerationRequest,
    CourseAssessmentGenerationResult, CourseBlueprintGenerationRequest, CourseBlueprintGenerationResult,
    CourseContextDiagnosis, CourseContextDiagnosisRequest, CourseObjectiveGenerationRequest,
    CourseObjectiveGenerationResult, CoursePedagogyRecommendationRequest, CoursePedagogyRecommendationResult,
    CourseQualityCheckRequest, CourseQualityCheckResult,
)
from app.schemas.research_assistant import (
    EvidenceCardDraftResult, EvidenceCardGenerationRequest, EvidenceCardGenerationResponse,
    ResearchAnalysisPatch, ResearchAnalysisRequest, ResearchAnalysisResponse, ResearchAnalysisResult,
    ResearchAnalysisSupplementRequest, ResearchAnalysisSupplementResponse, ResearchChatRequest,
    ResearchChatResponse, ResearchChatResult,
)
from app.services.research_source_validation_service import validate_source_excerpt
from app.schemas.resource_creation import (
    ResourceBlockTransformProviderRequest, ResourceBlockTransformResult, ResourceRevisionProposalRequest,
    ResourceRevisionProposalResult, ResourceSettingsRecommendationRequest, ResourceSettingsRecommendationResult,
    ResourceType, TeachingResourceGenerationRequest, TeachingResourceGenerationResult, TeachingResourceReviewRequest,
    TeachingResourceReviewResult,
)


ModelT = TypeVar("ModelT", bound=BaseModel)
logger = logging.getLogger(__name__)


def normalize_resource_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize common resource nesting mistakes without weakening model validation."""
    title = payload.get("title")
    change_summary = payload.get("changeSummary", payload.get("change_summary"))
    content = payload.get("content")

    if isinstance(content, dict):
        if "blocks" not in content and "key" in content:
            normalized_content = {"title": title, "blocks": [content], "metadata": {}}
        else:
            normalized_content = {
                "title": content.get("title", title),
                "blocks": content.get("blocks", []),
                "metadata": content.get("metadata", {}),
            }
    elif "blocks" in payload:
        normalized_content = {
            "title": title,
            "blocks": payload.get("blocks"),
            "metadata": payload.get("metadata", {}),
        }
    elif "key" in payload:
        normalized_content = {
            "title": title,
            "blocks": [{
                "key": payload.get("key"),
                "title": payload.get("blockTitle"),
                "content": content,
            }],
            "metadata": {},
        }
    else:
        return {
            "title": title,
            "content": content,
            "changeSummary": change_summary,
        }

    if isinstance(normalized_content["blocks"], dict):
        normalized_content["blocks"] = [normalized_content["blocks"]]
    if isinstance(normalized_content["blocks"], list):
        normalized_content["blocks"] = [
            {
                key: block[key]
                for key in ("key", "title", "content")
                if key in block
            }
            if isinstance(block, dict) else block
            for block in normalized_content["blocks"]
        ]
    return {
        "title": title or normalized_content["title"],
        "content": normalized_content,
        "changeSummary": change_summary,
    }


class SparkResearchAssistant(ResearchAssistantProvider):
    """Provider-only adapter: prompts and validates, but never persists data."""

    def __init__(self, client: SparkLLMClient | None = None) -> None:
        self._client = client or SparkLLMClient()

    @property
    def provider_name(self) -> str:
        return "spark"

    async def analyze_research(self, request: ResearchAnalysisRequest) -> ResearchAnalysisResponse:
        result = await self._from_messages(build_research_analysis_messages(request), ResearchAnalysisResult)
        # Evidence readiness is a deterministic service concern, never an LLM decision.
        result = result.model_copy(update={"evidence_ready": False})
        source_text = request.analysis_evidence or request.extracted_text or ""
        result = result.model_copy(update={
            "source_excerpt": validate_source_excerpt(
                result.source_excerpt, source_text, resource_id=request.resource_id
            )
        })
        return ResearchAnalysisResponse(provider=self.provider_name, request_fingerprint=self._fingerprint(request), data=result)

    async def supplement_research_analysis(
        self, request: ResearchAnalysisSupplementRequest
    ) -> ResearchAnalysisSupplementResponse:
        result = await self._from_messages(
            build_research_analysis_supplement_messages(request), ResearchAnalysisPatch
        )
        return ResearchAnalysisSupplementResponse(
            provider=self.provider_name,
            request_fingerprint=self._fingerprint(request),
            data=result,
        )

    async def chat(self, request: ResearchChatRequest) -> ResearchChatResponse:
        result = await self._from_messages(build_research_chat_messages(request), ResearchChatResult)
        return ResearchChatResponse(provider=self.provider_name, request_fingerprint=self._fingerprint(request), data=result)

    async def stream_chat(self, request: ResearchChatRequest) -> AsyncIterator[str]:
        async for content in self._client.stream_chat(
            build_research_chat_stream_messages(request)
        ):
            yield content

    async def generate_evidence_card(self, request: EvidenceCardGenerationRequest) -> EvidenceCardGenerationResponse:
        result = await self._from_messages(build_evidence_card_messages(request), EvidenceCardDraftResult)
        if result.source_document != request.source_file_name:
            raise SparkContractError("Spark evidence card sourceDocument must equal source_file_name")
        return EvidenceCardGenerationResponse(provider=self.provider_name, request_fingerprint=self._fingerprint(request), data=result)

    async def diagnose_course_context(self, request: CourseContextDiagnosisRequest) -> CourseContextDiagnosis:
        return await self._from_messages(build_course_context_messages(request), CourseContextDiagnosis)

    async def generate_course_objectives(self, request: CourseObjectiveGenerationRequest) -> CourseObjectiveGenerationResult:
        standard_ids = self._ids(request.curriculum_standards)
        literacy_ids = self._ids(request.ai_literacy_items)
        return await self._from_messages(
            build_course_objective_messages(request), CourseObjectiveGenerationResult,
            lambda result: [
                (self._require_subset(item.standard_refs, standard_ids, "standardRefs"), self._require_subset(item.literacy_refs, literacy_ids, "literacyRefs"))
                for item in result.objectives
            ],
        )

    async def recommend_course_pedagogy(self, request: CoursePedagogyRecommendationRequest) -> CoursePedagogyRecommendationResult:
        method_ids = self._ids(request.methods)
        return await self._from_messages(
            build_course_pedagogy_messages(request), CoursePedagogyRecommendationResult,
            lambda result: [self._require_subset([item.method_id], method_ids, "pedagogy methodId") for item in [result.recommended, *result.alternatives]],
        )

    async def generate_course_assessments(self, request: CourseAssessmentGenerationRequest) -> CourseAssessmentGenerationResult:
        objective_ids = self._ids(request.objectives)
        return await self._from_messages(
            build_course_assessment_messages(request), CourseAssessmentGenerationResult,
            lambda result: [self._require_subset([item.objective_id], objective_ids, "objectiveId") for item in result.assessments],
        )

    async def generate_course_blueprint(self, request: CourseBlueprintGenerationRequest) -> CourseBlueprintGenerationResult:
        objective_ids = self._ids(request.objectives)
        return await self._from_messages(
            build_course_blueprint_messages(request), CourseBlueprintGenerationResult,
            lambda result: [self._require_subset(item.objective_refs, objective_ids, "objectiveRefs") for item in result.activities],
        )

    async def regenerate_course_activity(self, request: CourseActivityRegenerationRequest) -> CourseActivityProposal:
        return await self._from_messages(
            build_course_activity_regeneration_messages(request), CourseActivityProposal,
            lambda result: self._require_subset(result.objective_refs, self._ids(request.blueprint.objectives), "objectiveRefs"),
        )

    async def check_course_quality(self, request: CourseQualityCheckRequest) -> CourseQualityCheckResult:
        return await self._from_messages(build_course_quality_messages(request), CourseQualityCheckResult)

    async def generate_teaching_resource(self, request: TeachingResourceGenerationRequest) -> TeachingResourceGenerationResult:
        def validate(result: TeachingResourceGenerationResult) -> None:
            try:
                validate_generated_resource(request.resource_type, result.content, request)
            except ValueError as exc:
                raise SparkContractError(str(exc)) from exc

        try:
            messages = build_teaching_resource_messages(request)
        except Exception as exc:
            logger.exception("Teaching resource generation failed stage=prompt_build exception_type=%s resource_type=%s", type(exc).__name__, request.resource_type.value)
            raise
        try:
            return await self._from_messages(
                messages, TeachingResourceGenerationResult, validate,
                resource_type=request.resource_type,
            )
        except (SparkResponseParseError, SparkContractError) as exc:
            logger.exception("Teaching resource generation failed stage=schema_validation exception_type=%s resource_type=%s", type(exc).__name__, request.resource_type.value)
            raise
        except Exception as exc:
            logger.exception("Teaching resource generation failed stage=provider_call exception_type=%s resource_type=%s", type(exc).__name__, request.resource_type.value)
            raise

    async def recommend_resource_settings(self, request: ResourceSettingsRecommendationRequest) -> ResourceSettingsRecommendationResult:
        return await self._structured("resource settings recommendation", request, ResourceSettingsRecommendationResult)

    async def transform_resource_block(self, request: ResourceBlockTransformProviderRequest) -> ResourceBlockTransformResult:
        return await self._structured("resource block transform", request, ResourceBlockTransformResult)

    async def review_teaching_resource(self, request: TeachingResourceReviewRequest) -> TeachingResourceReviewResult:
        return await self._structured("teaching resource review", request, TeachingResourceReviewResult)

    async def propose_resource_revision(self, request: ResourceRevisionProposalRequest) -> ResourceRevisionProposalResult:
        return await self._structured("resource revision proposal", request, ResourceRevisionProposalResult)

    async def _structured(self, task: str, request: BaseModel, result_type: type[ModelT]) -> ModelT:
        prompt = {
            "task": task,
            "rules": [
                "Return JSON only; no markdown and no explanation.",
                "Use camelCase keys exactly matching the supplied JSON schema.",
                "Do not invent evidence or database IDs.",
                "Return null only when resultSchema explicitly allows null; required fields and array minimums must satisfy resultSchema.",
                "For pedagogical interpretation tasks, reason only from the supplied teaching context.",
            ],
            "request": request.model_dump(mode="json", by_alias=True),
            "resultSchema": result_type.model_json_schema(by_alias=True),
        }
        return await self._from_messages([
            {"role": "system", "content": "You are a cautious education-research assistant. Follow the JSON contract exactly."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ], result_type)

    async def _from_messages(
        self, messages: list[dict[str, str]], result_type: type[ModelT],
        contract_validator: Callable[[ModelT], object] | None = None,
        resource_type: ResourceType | None = None,
    ) -> ModelT:
        try:
            if resource_type:
                payload = await self._resource_chat_json(
                    messages, resource_type=resource_type, repair_triggered=False
                )
            else:
                payload = await self._client.chat_json(messages, repair=False)
        except SparkResponseParseError as exc:
            logger.warning("Structured model output failed stage=json_parse exception_type=%s; attempting one repair", type(exc).__name__)
            return await self._repair_and_validate(
                messages, result_type, contract_validator, validation_error=str(exc),
                resource_type=resource_type,
            )
        return await self._validate_or_repair(
            messages, payload, result_type, contract_validator, resource_type=resource_type
        )

    async def _validate_or_repair(
        self, messages: list[dict[str, str]], payload: dict[str, Any], result_type: type[ModelT],
        contract_validator: Callable[[ModelT], object] | None,
        *, resource_type: ResourceType | None = None,
    ) -> ModelT:
        if result_type is TeachingResourceGenerationResult:
            normalized = normalize_resource_payload(payload)
            normalize_result = "changed" if normalized != payload else "unchanged"
            if resource_type == ResourceType.ASSESSMENT and isinstance(normalized.get("content"), dict):
                assessment_content = normalize_assessment_content(normalized["content"])
                if assessment_content != normalized["content"]:
                    normalize_result = "changed"
                normalized["content"] = assessment_content
            logger.info(
                "Resource payload normalized resource_type=%s normalize_result=%s repair_triggered=false",
                resource_type.value if resource_type else None,
                normalize_result,
            )
            payload = normalized
        try:
            result = result_type.model_validate(payload, extra="forbid")
            if contract_validator is not None:
                contract_validator(result)
            return result
        except (ValidationError, SparkContractError) as exc:
            logger.warning("Structured model output failed stage=schema_validation exception_type=%s; attempting one repair", type(exc).__name__)
            return await self._repair_and_validate(
                messages,
                result_type,
                contract_validator,
                invalid_payload=payload,
                validation_error=self._brief_validation_error(exc),
                resource_type=resource_type,
            )

    async def _repair_and_validate(
        self, messages: list[dict[str, str]], result_type: type[ModelT],
        contract_validator: Callable[[ModelT], object] | None,
        *,
        invalid_payload: dict[str, Any] | None = None,
        validation_error: str | None = None,
        resource_type: ResourceType | None = None,
    ) -> ModelT:
        repair_request: dict[str, Any] = {
            "task": "Repair the previous invalid output once. Return only one JSON object satisfying the contract.",
            "invalidPayload": invalid_payload,
            "validationError": validation_error,
        }
        if result_type is TeachingResourceGenerationResult:
            if resource_type == ResourceType.ASSESSMENT:
                invalid_json: object = invalid_payload
                if isinstance(invalid_payload, dict):
                    content = invalid_payload.get("content")
                    blocks = content.get("blocks") if isinstance(content, dict) else None
                    invalid_json = [
                        block for block in blocks
                        if isinstance(block, dict) and block.get("key") in {"criteria", "rubric", "evidence"}
                    ] if isinstance(blocks, list) else content
                repair_request.pop("invalidPayload", None)
                repair_request.update({
                    "task": "Fix JSON structure only. Do not regenerate or rewrite the teaching content.",
                    "invalidBlockJson": invalid_json,
                    "outputTemplate": RESOURCE_OUTPUT_TEMPLATES[ResourceType.ASSESSMENT],
                })
            else:
                repair_request.update({
                    "outputTemplate": RESOURCE_OUTPUT_TEMPLATES[resource_type] if resource_type else None,
                    "criticalStructureRules": TEACHING_RESOURCE_STRUCTURE_RULES,
                    "explicitCorrection": (
                        "content must be an object containing title/blocks/metadata; "
                        "key must be inside content.blocks and must not appear at root."
                    ),
                })
        else:
            repair_request["resultSchema"] = result_type.model_json_schema(by_alias=True)
        repair_messages = [
            {"role": "system", "content": "Repair one JSON object. Return JSON only."},
            {"role": "user", "content": json.dumps(repair_request, ensure_ascii=False)},
        ]
        if resource_type:
            repaired = await self._resource_chat_json(
                repair_messages, resource_type=resource_type, repair_triggered=True
            )
        else:
            repaired = await self._client.chat_json(repair_messages, repair=False)
        if result_type is TeachingResourceGenerationResult:
            repaired = normalize_resource_payload(repaired)
            if resource_type == ResourceType.ASSESSMENT and isinstance(repaired.get("content"), dict):
                repaired["content"] = normalize_assessment_content(repaired["content"])
        try:
            result = result_type.model_validate(repaired, extra="forbid")
            if contract_validator is not None:
                contract_validator(result)
            return result
        except (ValidationError, SparkContractError) as exc:
            raise SparkContractError("Spark JSON violates the required result contract") from exc

    @staticmethod
    def _brief_validation_error(exc: ValidationError | SparkContractError) -> str:
        if not isinstance(exc, ValidationError):
            return str(exc)
        errors = [
            {
                "location": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors(include_url=False)
        ]
        return json.dumps(errors, ensure_ascii=False)

    async def _resource_chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        resource_type: ResourceType,
        repair_triggered: bool,
    ) -> dict[str, Any]:
        token_limits = (
            settings.spark_resource_max_tokens,
            settings.spark_resource_retry_max_tokens,
        )
        for attempt, max_tokens in enumerate(token_limits, start=1):
            try:
                return await self._client.chat_json(
                    messages,
                    repair=False,
                    max_tokens=max_tokens,
                    performance_context={
                        "resource_type": resource_type.value,
                        "attempt": attempt,
                        "repair_triggered": repair_triggered,
                    },
                )
            except SparkOutputLengthError:
                if attempt == len(token_limits):
                    raise
                logger.warning(
                    "Retrying truncated resource output resource_type=%s attempt=%s requested_max_tokens=%s next_max_tokens=%s repair_triggered=%s",
                    resource_type.value, attempt, max_tokens, token_limits[attempt],
                    repair_triggered,
                )
        raise AssertionError("resource token retry loop exhausted")

    @staticmethod
    def _fingerprint(request: BaseModel) -> str:
        encoded = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _ids(items: list[dict[str, object]]) -> set[int]:
        return {item["id"] for item in items if isinstance(item.get("id"), int)}  # type: ignore[misc]

    @staticmethod
    def _require_subset(values: list[int], allowed: set[int], label: str) -> None:
        if not set(values).issubset(allowed):
            raise SparkContractError(f"Spark returned an unknown {label}")
