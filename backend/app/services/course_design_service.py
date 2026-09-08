from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.course_design import (
    ProjectActivity,
    ProjectAssessment,
    ProjectObjective,
    ProjectPedagogy,
    QualityCheck,
)
from app.repositories.project_repository import ProjectRepository
from app.services.project_service import ProjectNotFoundError


class CourseDesignWorkflowStateError(ValueError):
    pass


class CourseDesignService:
    """Read the complete persisted course-design state for one owned project."""

    _STEP_BY_WORKFLOW = {
        "DRAFT": (1, []),
        "RESEARCH_READY": (1, []),
        "CONTEXT_READY": (2, [1]),
        "OBJECTIVE_PENDING": (2, [1]),
        "OBJECTIVE_CONFIRMED": (3, [1, 2]),
        "PEDAGOGY_PENDING": (3, [1, 2]),
        "PEDAGOGY_CONFIRMED": (4, [1, 2, 3]),
        "ASSESSMENT_PENDING": (4, [1, 2, 3]),
        "ASSESSMENT_CONFIRMED": (5, [1, 2, 3, 4]),
        "ACTIVITY_READY": (5, [1, 2, 3, 4]),
        "QUALITY_READY": (6, [1, 2, 3, 4, 5]),
        "QUALITY_CHECKED": (6, [1, 2, 3, 4, 5, 6]),
        "ARTIFACT_READY": (6, [1, 2, 3, 4, 5, 6]),
        # Read compatibility for projects not yet passed through Step 1.
        "OBJECTIVE_READY": (3, [1, 2]),
        "PEDAGOGY_READY": (4, [1, 2, 3]),
        "ASSESSMENT_READY": (5, [1, 2, 3, 4]),
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)

    def get_course_design_state(self, *, current_user_id: int, project_id: int) -> dict[str, object]:
        project = self.projects.get_by_id_and_user(project_id=project_id, user_id=current_user_id)
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")

        objectives = self.db.scalars(
            select(ProjectObjective).where(ProjectObjective.project_id == project.id, or_(ProjectObjective.teacher_action.is_(None), ProjectObjective.teacher_action != "REJECT")).order_by(ProjectObjective.sequence_no, ProjectObjective.id)
        ).all()
        pedagogy = self.db.scalar(
            select(ProjectPedagogy).where(ProjectPedagogy.project_id == project.id).order_by(ProjectPedagogy.confirmed.desc(), ProjectPedagogy.id.desc()).limit(1)
        )
        assessments = self.db.scalars(
            select(ProjectAssessment).where(ProjectAssessment.project_id == project.id).order_by(ProjectAssessment.objective_id, ProjectAssessment.id)
        ).all()
        activities = self.db.scalars(
            select(ProjectActivity).where(ProjectActivity.project_id == project.id).order_by(ProjectActivity.sequence_no, ProjectActivity.id)
        ).all()
        quality_checks = self.db.scalars(
            select(QualityCheck).where(QualityCheck.project_id == project.id).order_by(QualityCheck.id)
        ).all()
        try:
            current_step, completed_steps = self._STEP_BY_WORKFLOW[project.workflow_state]
        except KeyError as exc:
            raise CourseDesignWorkflowStateError(
                f"Unsupported course-design workflow state: {project.workflow_state}"
            ) from exc

        return {
            "project": {"projectId": project.id, "title": project.title, "topic": project.topic, "projectType": project.project_type},
            "context": {
                "grade": project.grade, "classHours": project.class_hours,
                "lessonMinutes": project.lesson_minutes, "classSize": project.class_size,
                "studentLevel": project.student_level, "studentExperience": project.student_experience,
                "aiAccessMode": project.ai_access_mode, "devices": project.devices_json or [],
                "deviceCondition": self._device_condition(project.devices_json),
                "constraints": project.constraints_json or [], "additionalRequirements": project.additional_requirements,
            },
            "contextDiagnosis": project.context_diagnosis_json or {},
            "objectives": [self._objective(item) for item in objectives],
            "pedagogy": self._pedagogy(pedagogy),
            "assessments": [self._assessment(item) for item in assessments],
            "activities": [self._activity(item) for item in activities],
            "qualityChecks": [self._quality_check(item) for item in quality_checks],
            "workflowState": project.workflow_state,
            "staleSections": project.stale_sections_json or [],
            "currentStep": current_step,
            "completedSteps": completed_steps,
        }

    @staticmethod
    def _objective(item: ProjectObjective) -> dict[str, object]:
        return {"objectiveId": item.id, "content": item.content, "sequenceNo": item.sequence_no, "standardRefs": item.standard_refs_json or [], "literacyRefs": item.literacy_refs_json or [], "rationale": item.rationale, "sourceType": item.source_type, "teacherAction": item.teacher_action, "confirmed": item.confirmed, "version": item.version}

    @staticmethod
    def _pedagogy(item: ProjectPedagogy | None) -> dict[str, object]:
        if item is None:
            return {}
        return {"pedagogyId": item.id, "primaryMethodId": item.primary_method_id, "secondaryMethodId": item.secondary_method_id, "rationale": item.rationale, "suitableFor": item.suitable_for_json or [], "riskNote": item.risk_note, "alternatives": item.alternative_json, "teacherAction": item.teacher_action, "confirmed": item.confirmed, "version": item.version, "customName": item.custom_name, "customDescription": item.custom_description, "sourceType": item.source_type}

    @staticmethod
    def _assessment(item: ProjectAssessment) -> dict[str, object]:
        return {"assessmentId": item.id, "objectiveId": item.objective_id, "taskContent": item.task_content, "studentEvidence": item.student_evidence_json or [], "criteria": item.criteria_json or {}, "rationale": item.rationale, "teacherAction": item.teacher_action, "confirmed": item.confirmed, "version": item.version}

    @staticmethod
    def _activity(item: ProjectActivity) -> dict[str, object]:
        return {"activityId": item.id, "sequenceNo": item.sequence_no, "name": item.name, "duration": item.duration, "coreTask": item.core_task, "teacherAction": item.teacher_action, "studentAction": item.student_action, "aiRole": item.ai_role, "dominantActor": item.dominant_actor, "assessmentNote": item.assessment_note, "scaffolds": item.scaffolds_json or [], "objectiveRefs": item.objective_refs_json or [], "version": item.version}

    @staticmethod
    def _quality_check(item: QualityCheck) -> dict[str, object]:
        return {"qualityCheckId": item.id, "checkType": item.check_type, "status": item.status, "issue": item.issue, "reason": item.reason, "suggestion": item.suggestion, "evidence": item.evidence_json, "createdAt": item.created_at}

    @staticmethod
    def _device_condition(devices: list | None) -> str | None:
        if not devices:
            return None
        return str(devices[0])
