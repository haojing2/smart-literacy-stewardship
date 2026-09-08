from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class CourseDesignSchema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True, str_strip_whitespace=True)


class CourseDesignProject(CourseDesignSchema):
    project_id: int
    title: str
    topic: str
    project_type: str


class CourseDesignContext(CourseDesignSchema):
    grade: int | None = None
    class_hours: int | None = None
    lesson_minutes: int | None = None
    class_size: int | None = None
    student_level: str | None = None
    student_experience: str | None = None
    ai_access_mode: str | None = None
    device_condition: str | None = None
    devices: list[Any] = Field(default_factory=list)
    constraints: list[Any] = Field(default_factory=list)
    additional_requirements: str | None = None


class CourseContextDiagnosis(CourseDesignSchema):
    core_problem: str = Field(min_length=1)
    existing_foundation: str = Field(min_length=1)
    learning_difficulties: list[str] = Field(min_length=1)
    constraints: list[str] = Field(min_length=1)


class CourseContextDiagnosisRequest(CourseDesignSchema):
    project_id: int = Field(gt=0)
    grade: int = Field(gt=0)
    topic: str = Field(min_length=1)
    lesson_minutes: int = Field(gt=0)
    class_size: int = Field(gt=0)
    student_experience: str = Field(min_length=1)
    device_condition: str = Field(min_length=1)
    additional_requirements: str = ""
    prompt: str = Field(min_length=1)


class CourseObjectiveProposal(CourseDesignSchema):
    content: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    standard_refs: list[int] = Field(default_factory=list)
    literacy_refs: list[int] = Field(default_factory=list)


class CourseObjectiveGenerationRequest(CourseDesignSchema):
    project_id: int = Field(gt=0)
    grade: int = Field(gt=0)
    topic: str = Field(min_length=1)
    context_diagnosis: CourseContextDiagnosis
    evidence: list[dict[str, str]] = Field(default_factory=list)
    curriculum_standards: list[dict[str, object]] = Field(default_factory=list)
    ai_literacy_items: list[dict[str, object]] = Field(default_factory=list)
    prompt: str = Field(min_length=1)


class CourseObjectiveGenerationResult(CourseDesignSchema):
    objectives: list[CourseObjectiveProposal] = Field(min_length=2, max_length=4)


class CourseObjectiveUpdateRequest(CourseDesignSchema):
    content: str = Field(min_length=1)
    action: str = Field(pattern="^REVISE$")


class CourseObjectiveCreateRequest(CourseDesignSchema):
    content: str = Field(min_length=1)


class CoursePedagogyRecommendation(CourseDesignSchema):
    method_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    components: list[str] = Field(min_length=1)


class CoursePedagogyRecommendationRequest(CourseDesignSchema):
    project_id: int = Field(gt=0)
    context: dict[str, object]
    objectives: list[dict[str, object]] = Field(min_length=1)
    evidence: list[dict[str, str]] = Field(default_factory=list)
    methods: list[dict[str, object]] = Field(min_length=1)
    prompt: str = Field(min_length=1)


class CoursePedagogyRecommendationResult(CourseDesignSchema):
    recommended: CoursePedagogyRecommendation
    alternatives: list[CoursePedagogyRecommendation] = Field(default_factory=list)


class CoursePedagogySelectRequest(CourseDesignSchema):
    method_id: int = Field(gt=0)


class CoursePedagogyCustomRequest(CourseDesignSchema):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)


class CourseAssessmentProposal(CourseDesignSchema):
    objective_id: int = Field(gt=0)
    task_content: str = Field(min_length=1)
    student_evidence: list[str] = Field(min_length=1)
    criteria: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class CourseAssessmentGenerationRequest(CourseDesignSchema):
    project_id: int = Field(gt=0)
    context: dict[str, object]
    objectives: list[dict[str, object]] = Field(min_length=1)
    pedagogy: dict[str, object]
    ai_literacy_items: list[dict[str, object]] = Field(default_factory=list)
    evidence: list[dict[str, str]] = Field(default_factory=list)
    prompt: str = Field(min_length=1)


class CourseAssessmentGenerationResult(CourseDesignSchema):
    assessments: list[CourseAssessmentProposal] = Field(min_length=1)


class CourseAssessmentUpdateRequest(CourseDesignSchema):
    task_content: str | None = Field(default=None, min_length=1)
    student_evidence: list[str] | None = None
    criteria: list[str] | None = None

    @model_validator(mode="after")
    def require_a_change(self):
        if self.task_content is None and self.student_evidence is None and self.criteria is None:
            raise ValueError("At least one assessment field must be supplied")
        return self


class CourseActivityProposal(CourseDesignSchema):
    name: str = Field(min_length=1, max_length=255)
    duration: int = Field(gt=0)
    core_task: str = Field(min_length=1)
    teacher_action: str = Field(min_length=1)
    student_action: str = Field(min_length=1)
    ai_role: str = Field(min_length=1, max_length=64)
    assessment: str = Field(min_length=1)
    scaffolds: list[str] = Field(default_factory=list)
    objective_refs: list[int] = Field(default_factory=list)


class CourseBlueprintGenerationRequest(CourseDesignSchema):
    project_id: int = Field(gt=0)
    context: dict[str, object]
    objectives: list[dict[str, object]] = Field(min_length=1)
    pedagogy: dict[str, object]
    assessments: list[dict[str, object]] = Field(min_length=1)
    evidence: list[dict[str, str]] = Field(default_factory=list)
    prompt: str = Field(min_length=1)


class CourseBlueprintGenerationResult(CourseDesignSchema):
    activities: list[CourseActivityProposal] = Field(min_length=4, max_length=4)


class CourseActivityRegenerationRequest(CourseDesignSchema):
    blueprint: CourseBlueprintGenerationRequest
    activity: CourseActivityProposal
    previous_activity: CourseActivityProposal | None = None
    next_activity: CourseActivityProposal | None = None


class CourseActivityTransformRequest(CourseDesignSchema):
    action: str = Field(pattern="^(SHORTEN|INCREASE_DIFFICULTY|DECREASE_DIFFICULTY|ADD_SCAFFOLD)$")


class CourseActivityUpdateRequest(CourseDesignSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    duration: int | None = Field(default=None, gt=0)
    core_task: str | None = Field(default=None, min_length=1)
    teacher_action: str | None = Field(default=None, min_length=1)
    student_action: str | None = Field(default=None, min_length=1)
    ai_role: str | None = Field(default=None, min_length=1, max_length=64)
    assessment: str | None = Field(default=None, min_length=1)
    scaffolds: list[str] | None = None

    @model_validator(mode="after")
    def require_a_change(self):
        if all(
            value is None
            for value in (
                self.name, self.duration, self.core_task, self.teacher_action,
                self.student_action, self.ai_role, self.assessment, self.scaffolds,
            )
        ):
            raise ValueError("At least one activity field must be supplied")
        return self


class CourseQualityCheckProposal(CourseDesignSchema):
    check_type: str = Field(min_length=1, max_length=64)
    status: str = Field(pattern="^(PASS|WARNING)$")
    issue: str | None = None
    reason: str | None = None
    suggestion: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class CourseQualityCheckRequest(CourseDesignSchema):
    project_id: int = Field(gt=0)
    context: dict[str, object]
    objectives: list[dict[str, object]] = Field(min_length=1)
    pedagogy: dict[str, object]
    assessments: list[dict[str, object]] = Field(min_length=1)
    activities: list[dict[str, object]] = Field(min_length=1)
    evidence: list[dict[str, str]] = Field(default_factory=list)
    prompt: str = Field(min_length=1)


class CourseQualityCheckResult(CourseDesignSchema):
    checks: list[CourseQualityCheckProposal] = Field(min_length=1)


class CourseDesignObjective(CourseDesignSchema):
    objective_id: int
    content: str
    sequence_no: int
    standard_refs: list[Any] = Field(default_factory=list)
    literacy_refs: list[Any] = Field(default_factory=list)
    rationale: str | None = None
    source_type: str
    teacher_action: str | None = None
    confirmed: bool
    version: int


class CourseDesignPedagogy(CourseDesignSchema):
    pedagogy_id: int | None = None
    primary_method_id: int | None = None
    secondary_method_id: int | None = None
    rationale: str | None = None
    suitable_for: list[Any] = Field(default_factory=list)
    risk_note: str | None = None
    alternatives: dict[str, Any] | list[Any] | None = None
    teacher_action: str | None = None
    confirmed: bool | None = None
    version: int | None = None
    custom_name: str | None = None
    custom_description: str | None = None
    source_type: str | None = None


class CourseDesignAssessment(CourseDesignSchema):
    assessment_id: int
    objective_id: int
    task_content: str
    student_evidence: list[Any] = Field(default_factory=list)
    criteria: dict[str, Any] | list[Any] = Field(default_factory=list)
    rationale: str | None = None
    teacher_action: str | None = None
    confirmed: bool
    version: int


class CourseDesignActivity(CourseDesignSchema):
    activity_id: int
    sequence_no: int
    name: str
    duration: int
    core_task: str | None = None
    teacher_action: str | None = None
    student_action: str | None = None
    ai_role: str
    dominant_actor: str
    assessment_note: str | None = None
    scaffolds: list[Any] = Field(default_factory=list)
    objective_refs: list[Any] = Field(default_factory=list)
    version: int


class CourseDesignQualityCheck(CourseDesignSchema):
    quality_check_id: int
    check_type: str
    status: str
    issue: str | None = None
    reason: str | None = None
    suggestion: str | None = None
    evidence: dict[str, Any] | list[Any] | None = None
    created_at: datetime


class CourseDesignState(CourseDesignSchema):
    project: CourseDesignProject
    context: CourseDesignContext
    context_diagnosis: dict[str, Any] = Field(default_factory=dict)
    objectives: list[CourseDesignObjective] = Field(default_factory=list)
    pedagogy: CourseDesignPedagogy = Field(default_factory=CourseDesignPedagogy)
    assessments: list[CourseDesignAssessment] = Field(default_factory=list)
    activities: list[CourseDesignActivity] = Field(default_factory=list)
    quality_checks: list[CourseDesignQualityCheck] = Field(default_factory=list)
    workflow_state: str
    stale_sections: list[str] = Field(default_factory=list)
    current_step: int
    completed_steps: list[int] = Field(default_factory=list)
