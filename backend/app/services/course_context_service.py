from __future__ import annotations

from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.assistants.base import ResearchAssistantProvider
from app.models.course_project import CourseProject
from app.repositories.project_repository import ProjectRepository
from app.schemas.course_design import CourseContextDiagnosis, CourseContextDiagnosisRequest
from app.schemas.project import ProjectContextRequest
from app.services.project_service import ProjectNotFoundError
from app.services.workflow_service import WorkflowService


class ContextDiagnosisMissingError(ValueError):
    pass


class ContextIncompleteError(ValueError):
    pass


class CourseContextService:
    """Persist, diagnose, and confirm the first course-design stage."""

    _DIAGNOSIS_PROMPT = """根据提供的教学情境做简洁、教师可理解的诊断。
仅输出 JSON，字段必须是 coreProblem、existingFoundation、learningDifficulties、constraints。
不要生成完整教案、教学目标或教学策略。learningDifficulties 必须是具有可教学意义的学习困难。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)

    def save_context(
        self, *, current_user_id: int, project_id: int, payload: ProjectContextRequest
    ) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        stale_sections = WorkflowService.stale_sections_after_design_basis_change(
            project.workflow_state, project.stale_sections_json
        )
        try:
            project = self.projects.save_course_design_context(
                project,
                grade=payload.grade,
                topic=payload.topic,
                lesson_minutes=payload.lesson_minutes,
                class_size=payload.class_size,
                student_experience=payload.student_experience,
                device_condition=payload.device_condition,
                additional_requirements=payload.additional_requirements,
                workflow_state=project.workflow_state,
                stale_sections_json=stale_sections,
            )
            self.db.commit()
            self.db.refresh(project)
        except Exception:
            self.db.rollback()
            raise
        return self._result(project)

    async def diagnose_context(
        self,
        *,
        current_user_id: int,
        project_id: int,
        provider: ResearchAssistantProvider,
    ) -> CourseContextDiagnosis:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        request = self._diagnosis_request(project)
        diagnosis = await provider.diagnose_course_context(request)
        # Validate provider output again at the persistence boundary.
        diagnosis = CourseContextDiagnosis.model_validate(diagnosis)
        try:
            project.context_diagnosis_json = diagnosis.model_dump(by_alias=True, mode="json")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return diagnosis

    def confirm_context(self, *, current_user_id: int, project_id: int) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        self._diagnosis_request(project)
        if not project.context_diagnosis_json:
            raise ContextDiagnosisMissingError("Teaching-context diagnosis is required before confirmation")
        CourseContextDiagnosis.model_validate(project.context_diagnosis_json)
        try:
            if project.workflow_state == "DRAFT":
                project.workflow_state = "CONTEXT_READY"
            self.db.commit()
            self.db.refresh(project)
        except Exception:
            self.db.rollback()
            raise
        return self._result(project)

    def _owned_project(self, *, current_user_id: int, project_id: int) -> CourseProject:
        project = self.projects.get_by_id_and_user(project_id=project_id, user_id=current_user_id)
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return project

    @classmethod
    def _diagnosis_request(cls, project: CourseProject) -> CourseContextDiagnosisRequest:
        device_condition = str((project.devices_json or [""])[0])
        try:
            return CourseContextDiagnosisRequest(
                project_id=project.id,
                grade=project.grade or 0,
                topic=project.topic,
                lesson_minutes=project.lesson_minutes or 0,
                class_size=project.class_size or 0,
                student_experience=project.student_experience or "",
                device_condition=device_condition,
                additional_requirements=project.additional_requirements or "",
                prompt=cls._DIAGNOSIS_PROMPT,
            )
        except ValidationError as exc:
            raise ContextIncompleteError("Teaching context is incomplete") from exc

    @staticmethod
    def _result(project: CourseProject) -> dict[str, object]:
        return {
            "projectId": project.id,
            "workflowState": project.workflow_state,
            "staleSections": project.stale_sections_json or [],
            "updatedAt": project.updated_at,
        }
