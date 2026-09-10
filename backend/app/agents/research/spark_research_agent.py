from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.agents.research.base import ResearchAgentProvider
from app.agents.research.errors import (
    ResearchAgentContractError,
    ResearchAgentParseError,
)
from app.agents.research.spark_agent_client import SparkResearchAgentClient
from app.assistants.prompts.research import (
    build_research_analysis_messages,
    build_research_chat_messages,
    build_research_chat_stream_messages,
    build_research_conversation_summary_messages,
)
from app.schemas.research_assistant import (
    ResearchAnalysisRequest,
    ResearchAnalysisResponse,
    ResearchAnalysisResult,
    ResearchChatRequest,
    ResearchChatResponse,
    ResearchChatResult,
    ResearchConversationSummaryRequest,
    ResearchConversationSummaryResponse,
    ResearchConversationSummaryResult,
)
from app.services.research_source_validation_service import validate_source_excerpt


ModelT = TypeVar("ModelT", bound=BaseModel)
logger = logging.getLogger(__name__)


class SparkResearchAgent(ResearchAgentProvider):
    """研教智联 adapter for the Spark Assistant WebSocket API."""

    def __init__(self, client: SparkResearchAgentClient | None = None) -> None:
        self._client = client or SparkResearchAgentClient()

    @property
    def provider_name(self) -> str:
        return "spark_assistant"

    async def analyze_research(
        self, request: ResearchAnalysisRequest
    ) -> ResearchAnalysisResponse:
        result = await self._from_messages(
            build_research_analysis_messages(request), ResearchAnalysisResult
        )
        # Readiness is determined by application rules, never by Assistant text.
        result = result.model_copy(update={"evidence_ready": False})
        result = result.model_copy(update={
            "source_excerpt": validate_source_excerpt(
                result.source_excerpt,
                request.analysis_evidence or request.extracted_text or "",
                resource_id=request.resource_id,
            )
        })
        return ResearchAnalysisResponse(
            provider=self.provider_name,
            request_fingerprint=self._fingerprint(request),
            data=result,
        )

    async def chat(self, request: ResearchChatRequest) -> ResearchChatResponse:
        messages = self._assistant_messages(build_research_chat_messages(request))
        self._log_final_messages(request, messages)
        content = await self._client.generate(messages)
        try:
            payload = SparkResearchAgentClient.extract_json_object(content)
            result = ResearchChatResult.model_validate(payload, extra="forbid")
        except (ResearchAgentParseError, ValidationError):
            # The configured Research Agent commonly returns a normal answer.
            # Structured analysis enrichment is optional and must never make
            # an otherwise successful conversation fail.
            result = ResearchChatResult(
                message=content,
                analysis_patch=None,
                evidence_interpretations=[],
            )
        return ResearchChatResponse(
            provider=self.provider_name,
            request_fingerprint=self._fingerprint(request),
            data=result,
        )

    async def summarize_conversation(
        self, request: ResearchConversationSummaryRequest
    ) -> ResearchConversationSummaryResponse:
        result = await self._from_messages(
            build_research_conversation_summary_messages(request),
            ResearchConversationSummaryResult,
        )
        return ResearchConversationSummaryResponse(
            provider=self.provider_name,
            request_fingerprint=self._fingerprint(request),
            data=result,
        )

    async def stream_chat(self, request: ResearchChatRequest) -> AsyncIterator[str]:
        messages = self._assistant_messages(build_research_chat_stream_messages(request))
        self._log_final_messages(request, messages)
        content = await self._client.generate(messages)
        if not content.strip():
            raise ResearchAgentContractError("Research Agent stream response is empty")
        # The Assistant SDK call is non-streaming by design.  The endpoint keeps
        # its SSE contract by emitting the complete Assistant answer as one event.
        yield content

    async def _from_messages(
        self,
        messages: list[dict[str, str]],
        result_type: type[ModelT],
    ) -> ModelT:
        assistant_messages = self._assistant_messages(messages)
        content = await self._client.generate(assistant_messages)
        try:
            payload = SparkResearchAgentClient.extract_json_object(
                content
            )
            return result_type.model_validate(payload, extra="forbid")
        except (ResearchAgentParseError, ValidationError) as initial_error:
            self._log_contract_failure(
                phase="initial", result_type=result_type,
                content=content, error=initial_error,
            )
            repaired_messages = [
                *assistant_messages,
                {
                    "role": "user",
                    "content": self._repair_instruction(initial_error),
                },
            ]
            repaired_content = await self._client.generate(repaired_messages)
            try:
                repaired = SparkResearchAgentClient.extract_json_object(
                    repaired_content
                )
                return result_type.model_validate(repaired, extra="forbid")
            except (ResearchAgentParseError, ValidationError) as exc:
                self._log_contract_failure(
                    phase="repair", result_type=result_type,
                    content=repaired_content, error=exc,
                )
                raise ResearchAgentContractError(
                    "Research Agent JSON violates the required result contract"
                ) from exc

    @staticmethod
    def _validation_errors(error: ValidationError) -> list[dict[str, object]]:
        return [
            {"loc": list(item["loc"]), "type": item["type"], "message": item["msg"]}
            for item in error.errors(include_url=False, include_input=False)
        ]

    @classmethod
    def _repair_instruction(cls, error: Exception) -> str:
        if isinstance(error, ValidationError):
            details = "\n".join(
                f"- {'.'.join(map(str, item['loc']))}: {item['message']} ({item['type']})"
                for item in cls._validation_errors(error)
            )
        else:
            details = f"- JSON parse error: {error}"
        return (
            "上一条 JSON 未通过验证。\n具体错误：\n"
            f"{details}\n请重新返回完整 JSON。只能使用 resultSchema 中允许的字段。"
            "不要 Markdown，不要解释。"
        )

    @classmethod
    def _log_contract_failure(
        cls, *, phase: str, result_type: type[BaseModel], content: str,
        error: Exception,
    ) -> None:
        if isinstance(error, ValidationError):
            logger.warning(
                "Research Agent contract validation failed phase=%s result_type=%s "
                "response_chars=%s error_type=%s validation_errors=%s",
                phase, result_type.__name__, len(content), type(error).__name__,
                cls._validation_errors(error),
            )
        else:
            logger.warning(
                "Research Agent JSON parse failed phase=%s result_type=%s "
                "response_chars=%s error_type=%s content_prefix=%r",
                phase, result_type.__name__, len(content), type(error).__name__,
                content[:400],
            )

    @staticmethod
    def _assistant_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Assistant agents use user/assistant messages, never an unverified system role."""
        system_parts: list[str] = []
        normalized: list[dict[str, str]] = []
        for item in messages:
            role = item.get("role")
            content = item.get("content", "").strip()
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
            elif role in {"user", "assistant"}:
                normalized.append({"role": role, "content": content})
        if system_parts:
            instruction = "[APPLICATION TASK]\n" + "\n\n".join(system_parts)
            last_user_index = next(
                (index for index in range(len(normalized) - 1, -1, -1)
                 if normalized[index]["role"] == "user"),
                None,
            )
            if last_user_index is not None:
                normalized[last_user_index] = {
                    "role": "user",
                    "content": instruction + "\n\n" + normalized[last_user_index]["content"],
                }
            else:
                normalized.append({"role": "user", "content": instruction})
        if not normalized:
            raise ResearchAgentContractError("Research Agent prompt is empty")
        return normalized

    @staticmethod
    def _log_final_messages(
        request: ResearchChatRequest, messages: list[dict[str, str]]
    ) -> None:
        logger.info(
            "Research Agent messages assembled project_id=%s session_id=%s resource_id=%s "
            "final_agent_message_roles=%s final_agent_message_count=%s",
            request.project_id,
            request.session_id,
            request.resource_id,
            [message["role"] for message in messages],
            len(messages),
        )


    @staticmethod
    def _fingerprint(request: BaseModel) -> str:
        encoded = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
