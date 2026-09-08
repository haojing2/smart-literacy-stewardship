from app.assistants.base import ResearchAssistantProvider
from app.schemas.evidence import EvidenceSourceMetadata
from app.schemas.research_assistant import (
    EvidenceCardGenerationRequest,
    EvidenceCardGenerationResponse,
    ResearchAnalysisRequest,
    ResearchAnalysisResponse,
    ResearchChatRequest,
    ResearchChatResponse,
)
from app.services.evidence_readiness_service import EvidenceReadinessService


class ResearchAssistantService:
    """Business facade depending only on the provider abstraction."""

    def __init__(self, provider: ResearchAssistantProvider) -> None:
        self.provider = provider

    async def analyze_research(
        self, request: ResearchAnalysisRequest
    ) -> ResearchAnalysisResponse:
        return await self.provider.analyze_research(request)

    async def chat(self, request: ResearchChatRequest) -> ResearchChatResponse:
        return await self.provider.chat(request)

    async def generate_evidence_card(
        self,
        request: EvidenceCardGenerationRequest,
        *,
        source_metadata: EvidenceSourceMetadata,
    ) -> EvidenceCardGenerationResponse:
        EvidenceReadinessService.require_ready(
            request.analysis,
            source_metadata,
            expected_resource_id=request.resource_id,
        )
        return await self.provider.generate_evidence_card(request)
