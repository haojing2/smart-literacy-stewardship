from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ResourceCreationSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class ResourceType(StrEnum):
    PPT = "PPT"
    TEACHER_GUIDE = "TEACHER_GUIDE"
    WORKSHEET = "WORKSHEET"
    TASK_CARD = "TASK_CARD"
    AI_CASE = "AI_CASE"
    DISCUSSION = "DISCUSSION"
    ASSESSMENT = "ASSESSMENT"
    REFLECTION = "REFLECTION"


class ResourceCreationJobCreateRequest(ResourceCreationSchema):
    project_id: int = Field(gt=0)
    mode: Literal["COURSE_GENERATE"] = "COURSE_GENERATE"
    selected_types: list[ResourceType] = Field(default_factory=list)
    common_settings: dict[str, Any] = Field(default_factory=dict)
    resource_settings: dict[str, Any] = Field(default_factory=dict)


class ResourceCreationJobUpdateRequest(ResourceCreationSchema):
    current_step: int | None = Field(default=None, ge=1, le=255)
    selected_types: list[ResourceType] | None = None
    common_settings: dict[str, Any] | None = None
    resource_settings: dict[str, Any] | None = None
    status: str | None = Field(default=None, min_length=1, max_length=32)
    error_message: str | None = None


class ResourceCreationJobResponse(ResourceCreationSchema):
    job_id: int
    project_id: int
    user_id: int
    mode: str
    current_step: int
    selected_types: list[ResourceType] = Field(default_factory=list)
    common_settings: dict[str, Any] = Field(default_factory=dict)
    resource_settings: dict[str, Any] = Field(default_factory=dict)
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TeachingResourceResponse(ResourceCreationSchema):
    resource_id: int
    job_id: int
    project_id: int
    resource_type: ResourceType
    title: str
    settings: dict[str, Any] = Field(default_factory=dict)
    status: str
    current_version_no: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TeachingResourceVersionResponse(ResourceCreationSchema):
    version_id: int
    resource_id: int
    version_no: int
    content: "ResourceDraftContent"
    content_html: str | None = None
    change_source: str
    change_summary: str | None = None
    created_by: int
    created_at: datetime


class ResourceDraftBlock(ResourceCreationSchema):
    key: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=255)
    content: Any = None


class ResourceDraftContent(ResourceCreationSchema):
    title: str | None = Field(default=None, max_length=255)
    blocks: list[ResourceDraftBlock] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResourceCourseContext(ResourceCreationSchema):
    title: str = Field(min_length=1, max_length=255)
    topic: str | None = None
    grade: str | None = Field(default=None, max_length=64)
    lesson_minutes: int | None = Field(default=None, ge=1, le=1000)
    student_level: str | None = Field(default=None, max_length=255)
    devices: list[Any] = Field(default_factory=list)


class ResourceSettingsRecommendationRequest(ResourceCreationSchema):
    project: ResourceCourseContext
    selected_types: list[ResourceType] = Field(default_factory=list)
    common_settings: dict[str, Any] = Field(default_factory=dict)


class ResourceSettingsRecommendationResult(ResourceCreationSchema):
    recommendations: dict[str, Any] = Field(default_factory=dict)


class TeachingResourceGenerationRequest(ResourceCreationSchema):
    resource_type: ResourceType
    project: ResourceCourseContext
    objectives: list[dict[str, Any]] = Field(min_length=1)
    pedagogy: dict[str, Any]
    assessments: list[dict[str, Any]] = Field(min_length=1)
    activities: list[dict[str, Any]] = Field(min_length=1)
    common_settings: dict[str, Any] = Field(default_factory=dict)
    resource_settings: dict[str, Any] = Field(default_factory=dict)


class TeachingResourceGenerationResult(ResourceCreationSchema):
    title: str = Field(min_length=1, max_length=255)
    content: ResourceDraftContent
    change_summary: str | None = Field(default=None, max_length=2000)


class ResourceBlockTransformProviderRequest(ResourceCreationSchema):
    resource_type: ResourceType
    action: Literal["REGENERATE", "SIMPLIFY", "INCREASE_DIFFICULTY", "ADD_SCAFFOLD"]
    current_content: ResourceDraftContent
    target_block_key: str | None = Field(default=None, max_length=100)
    instruction: str | None = Field(default=None, max_length=4000)


class ResourceBlockTransformResult(ResourceCreationSchema):
    content: ResourceDraftContent
    change_summary: str = Field(min_length=1, max_length=2000)


class TeachingResourceReviewRequest(ResourceCreationSchema):
    resource_type: ResourceType
    content: ResourceDraftContent
    instruction: str | None = Field(default=None, max_length=4000)
    target_block_key: str | None = Field(default=None, max_length=100)


class ResourceRevisionProposal(ResourceCreationSchema):
    suggestion_type: str = Field(min_length=1, max_length=64)
    target_block_key: str | None = Field(default=None, max_length=100)
    issue: str | None = None
    reason: str | None = None
    suggested_content: str | None = None
    proposed_content: ResourceDraftContent


class TeachingResourceReviewResult(ResourceCreationSchema):
    proposals: list[ResourceRevisionProposal] = Field(default_factory=list)


class ResourceRevisionProposalRequest(ResourceCreationSchema):
    resource_type: ResourceType
    base_content: ResourceDraftContent
    user_request: str = Field(min_length=1, max_length=4000)
    target_block_key: str | None = Field(default=None, max_length=100)


class ResourceRevisionProposalResult(ResourceCreationSchema):
    proposal: ResourceRevisionProposal


class ResourceTransformRequest(ResourceCreationSchema):
    action: str = Field(min_length=1, max_length=64)
    target_block_key: str | None = Field(default=None, max_length=100)
    instruction: str | None = None
    content: ResourceDraftContent | None = None


class TeachingResourceVersionCreateRequest(ResourceCreationSchema):
    """Teacher-authored content. Saving always appends a new version."""

    content: ResourceDraftContent
    content_html: str | None = None
    change_summary: str | None = Field(default=None, max_length=2000)


class ResourceReviewRequest(ResourceCreationSchema):
    """Optional teacher focus used by the Mock AI review."""

    instruction: str | None = Field(default=None, max_length=4000)
    target_block_key: str | None = Field(default=None, max_length=100)


class ResourceReviewResponse(ResourceCreationSchema):
    resource: TeachingResourceResponse
    current_version: TeachingResourceVersionResponse | None = None
    suggestions: list["ResourceSuggestionResponse"] = Field(default_factory=list)


class ResourceSuggestionCreateRequest(ResourceCreationSchema):
    resource_id: int = Field(gt=0)
    base_version_id: int = Field(gt=0)
    target_block_key: str | None = Field(default=None, max_length=100)
    suggestion_type: str = Field(min_length=1, max_length=64)
    issue: str | None = None
    reason: str | None = None
    user_request: str | None = None
    suggested_content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResourceSuggestionResponse(ResourceCreationSchema):
    suggestion_id: int
    resource_id: int
    base_version_id: int
    target_block_key: str | None = None
    suggestion_type: str
    issue: str | None = None
    reason: str | None = None
    user_request: str | None = None
    suggested_content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str
    teacher_revision: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


class ResourceSuggestionReviseRequest(ResourceCreationSchema):
    status: Literal["ACCEPTED", "REVISED", "REJECTED"]
    teacher_revision: str | None = None


TeachingResourceVersionResponse.model_rebuild()
ResourceReviewResponse.model_rebuild()
