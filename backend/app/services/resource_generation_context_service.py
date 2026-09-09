from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course_design import ProjectActivity, ProjectAssessment, ProjectObjective, ProjectPedagogy
from app.models.course_project import CourseProject
from app.repositories.evidence_card_repository import EvidenceCardRepository
from app.schemas.resource_creation import ResourceType, TeachingResourceGenerationRequest
from app.services.project_service import ProjectNotFoundError


class ResourceGenerationContextService:
    """Build the model input exclusively from persisted, teacher-confirmed state."""

    _SETTINGS_KEYS = {
        ResourceType.TEACHER_GUIDE: "teacher-guide",
        ResourceType.WORKSHEET: "worksheet",
        ResourceType.TASK_CARD: "task-card",
        ResourceType.AI_CASE: "ai-case",
        ResourceType.DISCUSSION: "discussion",
        ResourceType.ASSESSMENT: "assessment",
        ResourceType.REFLECTION: "reflection",
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        *,
        project_id: int,
        current_user_id: int,
        resource_type: ResourceType | str,
        common_settings: dict[str, Any] | None,
        resource_settings: dict[str, Any] | None,
    ) -> TeachingResourceGenerationRequest:
        kind = ResourceType(resource_type)
        if kind == ResourceType.PPT:
            raise ValueError("PPT requires the dedicated PPT provider")
        project = self.db.scalar(
            select(CourseProject).where(
                CourseProject.id == project_id,
                CourseProject.user_id == current_user_id,
                CourseProject.is_deleted.is_(False),
            )
        )
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")

        objective_version = self.db.scalar(select(func.max(ProjectObjective.version)).where(
            ProjectObjective.project_id == project_id, ProjectObjective.confirmed.is_(True)
        ))
        objectives = list(self.db.scalars(select(ProjectObjective).where(
            ProjectObjective.project_id == project_id, ProjectObjective.confirmed.is_(True),
            ProjectObjective.version == objective_version,
        ).order_by(ProjectObjective.sequence_no)).all())
        pedagogy = self.db.scalar(select(ProjectPedagogy).where(
            ProjectPedagogy.project_id == project_id, ProjectPedagogy.confirmed.is_(True)
        ).order_by(ProjectPedagogy.version.desc(), ProjectPedagogy.id.desc()).limit(1))
        assessment_version = self.db.scalar(select(func.max(ProjectAssessment.version)).where(
            ProjectAssessment.project_id == project_id, ProjectAssessment.confirmed.is_(True)
        ))
        assessments = list(self.db.scalars(select(ProjectAssessment).where(
            ProjectAssessment.project_id == project_id, ProjectAssessment.confirmed.is_(True),
            ProjectAssessment.version == assessment_version,
        ).order_by(ProjectAssessment.id)).all())
        activity_version = self.db.scalar(select(func.max(ProjectActivity.version)).where(
            ProjectActivity.project_id == project_id
        ))
        activities = list(self.db.scalars(select(ProjectActivity).where(
            ProjectActivity.project_id == project_id, ProjectActivity.version == activity_version,
        ).order_by(ProjectActivity.sequence_no)).all())
        if not objectives or pedagogy is None or not assessments or not activities:
            from app.services.resource_creation_service import CourseDesignIncompleteError
            raise CourseDesignIncompleteError("Course design is incomplete")

        activity_data = [{
            "id": item.id, "sequenceNo": item.sequence_no, "name": item.name,
            "duration": item.duration, "coreTask": item.core_task,
            "teacherAction": item.teacher_action, "studentAction": item.student_action,
            "aiRole": item.ai_role, "dominantActor": item.dominant_actor,
            "assessmentNote": item.assessment_note, "scaffolds": item.scaffolds_json or [],
            "objectiveRefs": item.objective_refs_json or [],
        } for item in activities]
        evidence = [{
            "researchFinding": card.main_finding,
            "applicableAudience": card.participants,
            "recommendedStrategies": card.recommended_strategies_json or [],
            "implementationConditions": card.implementation_conditions_json or [],
            "teachingImplications": card.teaching_implication,
            "limitations": card.limitation,
            "source": card.source_document,
        } for card in EvidenceCardRepository(self.db).list_confirmed_by_project(project_id=project_id)]
        all_settings = resource_settings or {}
        own_settings = all_settings.get(self._SETTINGS_KEYS[kind], {})

        return TeachingResourceGenerationRequest.model_validate({
            "resourceType": kind,
            "project": {
                "title": project.title, "topic": project.topic, "grade": project.grade,
                "classHours": project.class_hours, "lessonMinutes": project.lesson_minutes,
                "studentLevel": project.student_level, "studentExperience": project.student_experience,
                "classSize": project.class_size, "aiAccessMode": project.ai_access_mode,
                "devices": project.devices_json or [], "constraints": project.constraints_json or [],
                "additionalRequirements": project.additional_requirements,
                "contextDiagnosis": project.context_diagnosis_json,
            },
            "objectives": [{
                "id": item.id, "content": item.content, "sequenceNo": item.sequence_no,
                "standardRefs": item.standard_refs_json or [], "literacyRefs": item.literacy_refs_json or [],
                "rationale": item.rationale,
            } for item in objectives],
            "pedagogy": {
                "id": pedagogy.id, "primaryMethodId": pedagogy.primary_method_id,
                "secondaryMethodId": pedagogy.secondary_method_id, "customName": pedagogy.custom_name,
                "description": pedagogy.custom_description or pedagogy.rationale,
                "suitableFor": pedagogy.suitable_for_json or [], "riskNote": pedagogy.risk_note,
            },
            "assessments": [{
                "id": item.id, "objectiveId": item.objective_id, "task": item.task_content,
                "studentEvidence": item.student_evidence_json or [], "criteria": item.criteria_json or [],
                "rationale": item.rationale,
            } for item in assessments],
            "activities": activity_data,
            "courseBlueprint": {
                "classHours": project.class_hours, "lessonMinutes": project.lesson_minutes,
                "totalActivityMinutes": sum(item.duration for item in activities),
                "activityOrder": [{"id": item.id, "sequenceNo": item.sequence_no, "name": item.name, "duration": item.duration} for item in activities],
            },
            "researchEvidence": evidence,
            "commonSettings": common_settings or {},
            "resourceSettings": own_settings if isinstance(own_settings, dict) else {},
        })
