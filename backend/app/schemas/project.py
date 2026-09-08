from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class ProjectSchema(BaseModel):
    """Base DTO: snake_case in Python and camelCase at the API boundary."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class ProjectType(StrEnum):
    NEW_TOPIC = "NEW_TOPIC"
    OPTIMIZE_EXISTING = "OPTIMIZE_EXISTING"
    TEXTBOOK_ADAPTATION = "TEXTBOOK_ADAPTATION"


class StudentLevel(StrEnum):
    BEGINNER = "BEGINNER"
    GENERAL = "GENERAL"
    ADVANCED = "ADVANCED"


class AiAccessMode(StrEnum):
    TEACHER_DEMO = "TEACHER_DEMO"
    GROUP = "GROUP"
    INDIVIDUAL = "INDIVIDUAL"


class ProjectCreateRequest(ProjectSchema):
    title: str = Field(min_length=1, max_length=255)
    topic: str = Field(min_length=1, max_length=255)
    project_type: ProjectType

    @field_validator("title", "topic")
    @classmethod
    def validate_non_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ProjectUpdateRequest(ProjectSchema):
    """Partial update DTO for editable project identity fields only."""

    title: str | None = Field(default=None, max_length=255)
    topic: str | None = Field(default=None, max_length=255)
    project_type: ProjectType | None = None

    @field_validator("title", "topic")
    @classmethod
    def validate_optional_non_blank_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class BasicProjectContextRequest(ProjectSchema):
    """The context collected by the project "basic information" step."""

    grade: int = Field(gt=0)
    class_hours: int = Field(gt=0)
    student_level: StudentLevel
    ai_access_mode: AiAccessMode
    devices: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    additional_requirements: str | None = Field(default=None, max_length=1000)


class ProjectContextRequest(ProjectSchema):
    """The richer context collected inside the course-design workspace.

    This has a distinct shape from :class:`BasicProjectContextRequest`, even
    though both are persisted against a project.  The endpoint accepts both
    shapes to keep the two UI workflows from validating each other's payload.
    """
    grade: int = Field(gt=0)
    topic: str = Field(min_length=1, max_length=255)
    lesson_minutes: int = Field(gt=0, le=600)
    class_size: int = Field(gt=0, le=500)
    student_experience: str = Field(min_length=1)
    device_condition: str = Field(min_length=1)
    additional_requirements: str = ""

    @field_validator("topic", "student_experience", "device_condition")
    @classmethod
    def validate_required_context_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("additional_requirements")
    @classmethod
    def normalize_optional_context_text(cls, value: str) -> str:
        return value.strip()


class ProjectCreateResponse(ProjectSchema):
    project_id: int
    workflow_state: str


class ProjectListItem(ProjectSchema):
    project_id: int
    title: str
    topic: str
    grade: int | None
    class_hours: int | None
    student_level: StudentLevel | None
    workflow_state: str
    updated_at: datetime


class ProjectDetailResponse(ProjectSchema):
    project_id: int
    title: str
    topic: str
    project_type: ProjectType
    grade: int | None
    class_hours: int | None
    student_level: StudentLevel | None
    ai_access_mode: AiAccessMode | None
    devices: list[str] | None
    constraints: list[str] | None
    additional_requirements: str | None
    workflow_state: str
    stale_sections: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProjectContextResponse(ProjectSchema):
    project_id: int
    workflow_state: str
    stale_sections: list[str] = Field(default_factory=list)
    updated_at: datetime


class ProjectWorkflowTransitionResponse(ProjectSchema):
    project_id: int
    workflow_state: str
    updated_at: datetime


class ProjectDeleteResponse(ProjectSchema):
    project_id: int
    deleted: bool


class ProjectUpdateResponse(ProjectSchema):
    project_id: int
    title: str
    topic: str
    project_type: ProjectType
    workflow_state: str
    stale_sections: list[str] = Field(default_factory=list)
    updated_at: datetime


class PaginationResponse(ProjectSchema):
    items: list[ProjectListItem]
    total: int = Field(ge=0)
    page: int = Field(gt=0)
    page_size: int = Field(gt=0)
