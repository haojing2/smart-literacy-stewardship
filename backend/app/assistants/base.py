from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.schemas.research_assistant import (
    EvidenceCardGenerationRequest,
    EvidenceCardGenerationResponse,
    ResearchAnalysisRequest,
    ResearchAnalysisResponse,
    ResearchAnalysisSupplementRequest,
    ResearchAnalysisSupplementResponse,
    ResearchChatRequest,
    ResearchChatResponse,
)
from app.schemas.course_design import (
    CourseContextDiagnosis,
    CourseContextDiagnosisRequest,
    CourseObjectiveGenerationRequest,
    CourseObjectiveGenerationResult,
    CoursePedagogyRecommendationRequest,
    CoursePedagogyRecommendationResult,
    CourseAssessmentGenerationRequest,
    CourseAssessmentGenerationResult,
    CourseActivityProposal,
    CourseActivityRegenerationRequest,
    CourseBlueprintGenerationRequest,
    CourseBlueprintGenerationResult,
    CourseQualityCheckRequest,
    CourseQualityCheckResult,
)
from app.schemas.resource_creation import (
    ResourceBlockTransformProviderRequest,
    ResourceBlockTransformResult,
    ResourceRevisionProposalRequest,
    ResourceRevisionProposalResult,
    ResourceSettingsRecommendationRequest,
    ResourceSettingsRecommendationResult,
    TeachingResourceGenerationRequest,
    TeachingResourceGenerationResult,
    TeachingResourceReviewRequest,
    TeachingResourceReviewResult,
)


class ResearchAssistantProvider(ABC):
    """Replaceable boundary for research-assistant capabilities."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def analyze_research(
        self, request: ResearchAnalysisRequest
    ) -> ResearchAnalysisResponse:
        raise NotImplementedError

    async def supplement_research_analysis(
        self, request: ResearchAnalysisSupplementRequest
    ) -> ResearchAnalysisSupplementResponse:
        """Fill requested missing fields without rewriting a full analysis."""
        raise NotImplementedError

    @abstractmethod
    async def chat(self, request: ResearchChatRequest) -> ResearchChatResponse:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat(self, request: ResearchChatRequest) -> AsyncIterator[str]:
        """Yield displayable assistant content for an open research conversation."""
        raise NotImplementedError

    @abstractmethod
    async def generate_evidence_card(
        self, request: EvidenceCardGenerationRequest
    ) -> EvidenceCardGenerationResponse:
        raise NotImplementedError

    @abstractmethod
    async def diagnose_course_context(
        self, request: CourseContextDiagnosisRequest
    ) -> CourseContextDiagnosis:
        """Return only a Pydantic-validated teaching-context diagnosis."""
        raise NotImplementedError

    @abstractmethod
    async def generate_course_objectives(
        self, request: CourseObjectiveGenerationRequest
    ) -> CourseObjectiveGenerationResult:
        raise NotImplementedError

    @abstractmethod
    async def recommend_course_pedagogy(
        self, request: CoursePedagogyRecommendationRequest
    ) -> CoursePedagogyRecommendationResult:
        raise NotImplementedError

    @abstractmethod
    async def generate_course_assessments(
        self, request: CourseAssessmentGenerationRequest
    ) -> CourseAssessmentGenerationResult:
        raise NotImplementedError

    @abstractmethod
    async def generate_course_blueprint(
        self, request: CourseBlueprintGenerationRequest
    ) -> CourseBlueprintGenerationResult:
        raise NotImplementedError

    @abstractmethod
    async def regenerate_course_activity(
        self, request: CourseActivityRegenerationRequest
    ) -> CourseActivityProposal:
        raise NotImplementedError

    @abstractmethod
    async def check_course_quality(
        self, request: CourseQualityCheckRequest
    ) -> CourseQualityCheckResult:
        raise NotImplementedError

    @abstractmethod
    async def generate_teaching_resource(
        self, request: TeachingResourceGenerationRequest
    ) -> TeachingResourceGenerationResult:
        """Generate a structured draft for one Mode A teaching resource."""
        raise NotImplementedError

    @abstractmethod
    async def recommend_resource_settings(
        self, request: ResourceSettingsRecommendationRequest
    ) -> ResourceSettingsRecommendationResult:
        raise NotImplementedError

    @abstractmethod
    async def transform_resource_block(
        self, request: ResourceBlockTransformProviderRequest
    ) -> ResourceBlockTransformResult:
        raise NotImplementedError

    @abstractmethod
    async def review_teaching_resource(
        self, request: TeachingResourceReviewRequest
    ) -> TeachingResourceReviewResult:
        raise NotImplementedError

    @abstractmethod
    async def propose_resource_revision(
        self, request: ResourceRevisionProposalRequest
    ) -> ResourceRevisionProposalResult:
        raise NotImplementedError
