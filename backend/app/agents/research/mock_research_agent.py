from __future__ import annotations

from collections.abc import AsyncIterator

from app.agents.research.base import ResearchAgentProvider
from app.assistants.mock_research_assistant import MockResearchAssistant
from app.schemas.research_assistant import (
    ResearchAnalysisRequest,
    ResearchAnalysisResponse,
    ResearchChatRequest,
    ResearchChatResponse,
    ResearchConversationSummaryRequest,
    ResearchConversationSummaryResponse,
    ResearchConversationSummaryResult,
)


class MockResearchAgent(ResearchAgentProvider):
    """Test/development implementation without the course-design surface."""

    def __init__(self, delegate: MockResearchAssistant | None = None) -> None:
        self._delegate = delegate or MockResearchAssistant()

    @property
    def provider_name(self) -> str:
        return "mock"

    async def analyze_research(self, request: ResearchAnalysisRequest) -> ResearchAnalysisResponse:
        return await self._delegate.analyze_research(request)

    async def chat(self, request: ResearchChatRequest) -> ResearchChatResponse:
        return await self._delegate.chat(request)

    async def summarize_conversation(
        self, request: ResearchConversationSummaryRequest
    ) -> ResearchConversationSummaryResponse:
        parts = [request.existing_summary] if request.existing_summary else []
        parts.extend(
            f"{message.role}: {message.content}"
            for message in request.messages
        )
        summary = "\n".join(parts)[-8000:] or "No prior discussion has been retained."
        payload = ResearchConversationSummaryResult(summary=summary)
        return ResearchConversationSummaryResponse(
            provider=self.provider_name,
            request_fingerprint=self._delegate._fingerprint(request),
            data=payload,
        )

    async def stream_chat(self, request: ResearchChatRequest) -> AsyncIterator[str]:
        async for content in self._delegate.stream_chat(request):
            yield content
