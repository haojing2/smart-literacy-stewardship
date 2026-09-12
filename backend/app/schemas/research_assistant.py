from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.schemas.evidence import EvidenceReadinessResult


class ResearchAssistantSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class ResearchAnalysisRequest(ResearchAssistantSchema):
    project_id: int | None = Field(default=None, gt=0)
    resource_id: int = Field(gt=0)
    analysis_evidence: str | None = Field(default=None, min_length=1)
    # Compatibility-only input for historical callers; new analysis uses bounded evidence.
    extracted_text: str | None = Field(default=None, min_length=1)
    project_title: str | None = None
    project_topic: str | None = None

    @model_validator(mode="after")
    def require_analysis_evidence(self):
        if not self.analysis_evidence and not self.extracted_text:
            raise ValueError("analysis_evidence is required")
        return self


class ResearchAnalysisResult(ResearchAssistantSchema):
    research_subjects: list[str] = Field(default_factory=list)
    research_topics: list[str] = Field(default_factory=list)
    ai_literacy_dimensions: list[str] = Field(default_factory=list)
    teaching_strategies: list[str] = Field(default_factory=list)
    intervention_duration: str | None = None
    assessment_tools: list[str] = Field(default_factory=list)
    main_findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    teaching_implications: str | None = None
    source_excerpt: str | None = None
    evidence_ready: bool = False


class ResearchAnalysisPatch(ResearchAssistantSchema):
    research_subjects: list[str] | None = None
    research_topics: list[str] | None = None
    ai_literacy_dimensions: list[str] | None = None
    teaching_strategies: list[str] | None = None
    intervention_duration: str | None = None
    assessment_tools: list[str] | None = None
    main_findings: list[str] | None = None
    limitations: list[str] | None = None
    teaching_implications: str | None = None


class ResearchAnalysisSupplementRequest(ResearchAssistantSchema):
    project_id: int | None = Field(default=None, gt=0)
    resource_id: int = Field(gt=0)
    analysis_batch: str | None = None
    retrieved_chunks: int | None = Field(default=None, ge=0)
    context_chars: int | None = Field(default=None, ge=0)
    missing_fields: list[str] = Field(min_length=1)
    analysis_evidence: str = Field(min_length=1)
    current_analysis: ResearchAnalysisResult


class ResearchChatMessageInput(ResearchAssistantSchema):
    role: Literal["USER", "SYSTEM", "ASSISTANT"]
    content: str = Field(min_length=1)


class ResearchConversationMessage(ResearchAssistantSchema):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ProjectKnowledgeSourceInput(ResearchAssistantSchema):
    content: str = Field(min_length=1)
    project_id: int | None = Field(default=None, gt=0)
    filename: str = Field(min_length=1)
    file_id: int = Field(gt=0)
    chunk_id: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    score: float


class ResearchChatRequest(ResearchAssistantSchema):
    project_id: int | None = Field(default=None, gt=0)
    session_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    message: str = Field(min_length=1)
    retrieval_query: str | None = None
    query_rewrite_status: Literal["READY", "FALLBACK", "FAILED"] = "FALLBACK"
    history: list[ResearchChatMessageInput] = Field(default_factory=list)
    analysis: ResearchAnalysisResult | None = None
    project_title: str | None = None
    project_topic: str | None = None
    grade: int | None = Field(default=None, ge=1, le=12)
    class_hours: int | None = Field(default=None, ge=1)
    student_level: str | None = None
    student_experience: str | None = None
    class_size: int | None = Field(default=None, ge=1)
    lesson_minutes: int | None = Field(default=None, ge=1)
    ai_access_mode: str | None = None
    devices: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    additional_requirements: str | None = None
    context_diagnosis: dict[str, Any] | None = None
    retrieval_scope: Literal["PROJECT", "RESOURCE"] = "PROJECT"
    retrieval_status: Literal["READY", "EMPTY", "FAILED"] = "EMPTY"
    conversation_summary: str | None = None
    conversation_context: str | None = None
    conversation_messages: list[ResearchConversationMessage] = Field(default_factory=list)
    project_knowledge_sources: list[ProjectKnowledgeSourceInput] = Field(
        default_factory=list
    )
    _search_project_documents_tool: Callable[[dict[str, Any]], Awaitable[Any]] | None = (
        PrivateAttr(default=None)
    )

    def bind_search_project_documents_tool(
        self, tool: Callable[[dict[str, Any]], Awaitable[Any]]
    ) -> None:
        self._search_project_documents_tool = tool

    async def execute_search_project_documents_tool(
        self, arguments: dict[str, Any]
    ) -> Any:
        if self._search_project_documents_tool is None:
            raise RuntimeError("Project document search is unavailable for this request")
        return await self._search_project_documents_tool(arguments)


class ResearchConversationSummaryRequest(ResearchAssistantSchema):
    existing_summary: str | None = None
    messages: list[ResearchChatMessageInput] = Field(default_factory=list)


class ResearchConversationSummaryResult(ResearchAssistantSchema):
    summary: str = Field(min_length=1, max_length=8000)


class EvidenceCardInterpretation(ResearchAssistantSchema):
    """Model-authored explanation anchored to one backend-supplied chunk."""

    chunk_id: str = Field(min_length=1)
    evidence_meaning: str = Field(min_length=1)
    relation_to_question: str = Field(min_length=1)
    synthesis: str = Field(min_length=1)


class ResearchChatResult(ResearchAssistantSchema):
    message: str
    analysis_patch: ResearchAnalysisPatch | None = None
    evidence_interpretations: list[EvidenceCardInterpretation] = Field(default_factory=list)


class EvidenceCardGenerationRequest(ResearchAssistantSchema):
    resource_id: int = Field(gt=0)
    source_file_name: str = Field(min_length=1)
    analysis: ResearchAnalysisResult


class EvidenceCardDraftResult(ResearchAssistantSchema):
    title: str
    topic: str | None = None
    participants: str | None = None
    main_finding: str | None = None
    limitation: str | None = None
    teaching_implication: str | None = None
    source_document: str
    source_text: str
    review_status: Literal["DRAFT"] = "DRAFT"


PayloadT = TypeVar("PayloadT", bound=BaseModel)


class ResearchAssistantResponse(ResearchAssistantSchema, Generic[PayloadT]):
    provider: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    data: PayloadT


ResearchAnalysisResponse = ResearchAssistantResponse[ResearchAnalysisResult]
ResearchAnalysisSupplementResponse = ResearchAssistantResponse[ResearchAnalysisPatch]
ResearchChatResponse = ResearchAssistantResponse[ResearchChatResult]
ResearchConversationSummaryResponse = ResearchAssistantResponse[ResearchConversationSummaryResult]
EvidenceCardGenerationResponse = ResearchAssistantResponse[EvidenceCardDraftResult]


ResearchAnalysisReadiness = EvidenceReadinessResult


class ResearchChatSessionCreateRequest(ResearchAssistantSchema):
    resource_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, max_length=255)


class ResearchChatMessageCreateRequest(ResearchAssistantSchema):
    content: str = Field(min_length=1)


class ResearchChatMessageResponse(ResearchAssistantSchema):
    message_id: int
    role: Literal["USER", "SYSTEM", "ASSISTANT"]
    sequence_no: int
    content: str
    metadata: dict[str, Any] | None = None
    created_at: datetime


class ResearchChatSessionResponse(ResearchAssistantSchema):
    session_id: int
    project_id: int
    resource_id: int | None = None
    title: str
    status: str
    messages: list[ResearchChatMessageResponse] = Field(default_factory=list)
    latest_analysis: ResearchAnalysisResult | None = None
    analysis_generation_status: Literal["PENDING", "READY", "FAILED"] | None = None
    readiness: ResearchAnalysisReadiness | None = None
    evidence_card_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ResearchChatSendMessageResponse(ResearchAssistantSchema):
    session_id: int
    user_message: ResearchChatMessageResponse
    assistant_message: ResearchChatMessageResponse
    analysis_patch: ResearchAnalysisPatch | None = None
    latest_analysis: ResearchAnalysisResult | None = None
    readiness: ResearchAnalysisReadiness | None = None
    evidence_draft_generated: bool = False
    evidence_card_id: int | None = None


class ResearchAnalysisEditRequest(ResearchAssistantSchema):
    participants: list[str]
    research_topic: str | None
    ai_literacy_dimensions: list[str]
    teaching_strategies: list[str]
    intervention: str | None
    assessment_tools: list[str]
    main_findings: list[str]
    limitations: list[str]

    @field_validator(
        "participants",
        "ai_literacy_dimensions",
        "teaching_strategies",
        "assessment_tools",
        "main_findings",
        "limitations",
    )
    @classmethod
    def clean_list_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @field_validator("research_topic", "intervention")
    @classmethod
    def empty_string_to_none(cls, value: str | None) -> str | None:
        return value or None


class ResearchAnalysisEditableView(ResearchAssistantSchema):
    participants: list[str]
    research_topic: str | None
    ai_literacy_dimensions: list[str]
    teaching_strategies: list[str]
    intervention: str | None
    assessment_tools: list[str]
    main_findings: list[str]
    limitations: list[str]


class ResearchAnalysisVersionResponse(ResearchAssistantSchema):
    session_id: int
    analysis_id: int
    version: int
    generation_status: Literal["PENDING", "READY", "FAILED"] = "READY"
    latest_analysis: ResearchAnalysisEditableView
    field_sources: dict[str, Literal["MOCK", "TEACHER"]]
    teacher_confirmed: bool
    teacher_confirmed_at: datetime | None = None
    readiness: ResearchAnalysisReadiness
    evidence_draft_generated: bool = False
    evidence_card_id: int | None = None
