from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.schemas.research_assistant import (
    ResearchAnalysisRequest,
    ResearchAnalysisResponse,
    ResearchChatRequest,
    ResearchChatResponse,
    ResearchConversationSummaryRequest,
    ResearchConversationSummaryResponse,
)


class ResearchAgentProvider(ABC):
    """AI capabilities required by 研教智联 and nothing else."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def analyze_research(self, request: ResearchAnalysisRequest) -> ResearchAnalysisResponse:
        raise NotImplementedError

    @abstractmethod
    async def chat(self, request: ResearchChatRequest) -> ResearchChatResponse:
        raise NotImplementedError

    @abstractmethod
    async def summarize_conversation(
        self, request: ResearchConversationSummaryRequest
    ) -> ResearchConversationSummaryResponse:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat(self, request: ResearchChatRequest) -> AsyncIterator[str]:
        raise NotImplementedError
