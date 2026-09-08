from __future__ import annotations

import hashlib
import json
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


ModelT = TypeVar("ModelT", bound=BaseModel)
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
        if result.source_excerpt:
            normalized_excerpt = self._normalize_source_text(result.source_excerpt)
            normalized_document = self._normalize_source_text(request.extracted_text)
            if normalized_excerpt not in normalized_document:
                # Keep the useful structured analysis but never persist an
                # excerpt that cannot be traced back to the extracted paper.
                result = result.model_copy(update={"source_excerpt": None})
        return ResearchAnalysisResponse(
            provider=self.provider_name,
            request_fingerprint=self._fingerprint(request),
            data=result,
        )

    async def chat(self, request: ResearchChatRequest) -> ResearchChatResponse:
        messages = self._assistant_messages(build_research_chat_messages(request))
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
        content = await self._client.generate(
            self._assistant_messages(build_research_chat_stream_messages(request))
        )
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
        try:
            content = await self._client.generate(assistant_messages)
            payload = SparkResearchAgentClient.extract_json_object(
                content
            )
            return result_type.model_validate(payload, extra="forbid")
        except (ResearchAgentParseError, ValidationError):
            repaired_messages = [
                *assistant_messages,
                {
                    "role": "user",
                    "content": (
                        "上一条回复未满足 JSON 输出契约。请仅返回一个完整 JSON 对象，"
                        "严格符合任务中的 resultSchema，不要 Markdown 或解释。"
                    ),
                },
            ]
            try:
                repaired = SparkResearchAgentClient.extract_json_object(
                    await self._client.generate(repaired_messages)
                )
                return result_type.model_validate(repaired, extra="forbid")
            except (ResearchAgentParseError, ValidationError) as exc:
                raise ResearchAgentContractError(
                    "Research Agent JSON violates the required result contract"
                ) from exc

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
            if normalized and normalized[0]["role"] == "user":
                normalized[0] = {
                    "role": "user",
                    "content": instruction + "\n\n" + normalized[0]["content"],
                }
            else:
                normalized.insert(0, {"role": "user", "content": instruction})
        if not normalized:
            raise ResearchAgentContractError("Research Agent prompt is empty")
        return normalized

    @staticmethod
    def _normalize_source_text(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _fingerprint(request: BaseModel) -> str:
        encoded = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
