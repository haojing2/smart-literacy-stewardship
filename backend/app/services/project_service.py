from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.repositories.project_repository import ProjectRepository
from app.services.workflow_service import WorkflowService


class ProjectNotFoundError(LookupError):
    """Raised when a project is absent or does not belong to the current user."""


class ProjectService:
    """Project use cases and transaction boundaries."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ProjectRepository(db)

    def create_project(
        self,
        *,
        current_user_id: int,
        title: str,
        topic: str,
        project_type: str,
    ) -> dict[str, int | str]:
        try:
            project = self.repository.create_project(
                user_id=current_user_id,
                title=title,
                topic=topic,
                project_type=project_type,
            )
            self.db.commit()
            self.db.refresh(project)
        except Exception:
            self.db.rollback()
            raise

        return {"projectId": project.id, "workflowState": project.workflow_state}

    def get_project(
        self, *, current_user_id: int, project_id: int
    ) -> dict[str, object]:
        project = self._get_owned_project(
            current_user_id=current_user_id, project_id=project_id
        )
        return self._project_detail(project)

    def list_projects(
        self,
        *,
        current_user_id: int,
        page: int,
        page_size: int,
        grade: int | None = None,
        keyword: str | None = None,
        sort: str | None = None,
    ) -> dict[str, object]:
        items, total = self.repository.list_by_user(
            user_id=current_user_id,
            page=page,
            page_size=page_size,
            grade=grade,
            keyword=keyword,
            sort=sort,
        )
        return {
            "items": [self._project_summary(project) for project in items],
            "total": total,
        }

    def save_context(
        self,
        *,
        current_user_id: int,
        project_id: int,
        grade: int | None,
        class_hours: int | None,
        student_level: str | None,
        ai_access_mode: str | None,
        devices: list | None,
        constraints: list | None,
        additional_requirements: str | None,
    ) -> dict[str, object]:
        project = self._get_owned_project(
            current_user_id=current_user_id, project_id=project_id
        )
        workflow_state, stale_sections = WorkflowService.context_save_result(
            project.workflow_state, project.stale_sections_json
        )

        try:
            project = self.repository.update_context(
                project,
                grade=grade,
                class_hours=class_hours,
                student_level=student_level,
                ai_access_mode=ai_access_mode,
                devices_json=devices,
                constraints_json=constraints,
                additional_requirements=additional_requirements,
                workflow_state=workflow_state,
                stale_sections_json=stale_sections,
            )
            self.db.commit()
            self.db.refresh(project)
        except Exception:
            self.db.rollback()
            raise

        return self._project_context_result(project)

    def update_project(
        self,
        *,
        current_user_id: int,
        project_id: int,
        title: str | None = None,
        topic: str | None = None,
        project_type: str | None = None,
    ) -> dict[str, object]:
        project = self._get_owned_project(
            current_user_id=current_user_id, project_id=project_id
        )

        title_changed = title is not None and title != project.title
        topic_changed = topic is not None and topic != project.topic
        project_type_changed = (
            project_type is not None and project_type != project.project_type
        )
        if not (title_changed or topic_changed or project_type_changed):
            return self._project_update_result(project)

        if topic_changed or project_type_changed:
            project.stale_sections_json = (
                WorkflowService.stale_sections_after_design_basis_change(
                    project.workflow_state, project.stale_sections_json
                )
            )

        try:
            project = self.repository.update_basic_info(
                project,
                title=project.title if title is None else title,
                topic=project.topic if topic is None else topic,
                project_type=project.project_type
                if project_type is None
                else project_type,
            )
            self.db.commit()
            self.db.refresh(project)
        except Exception:
            self.db.rollback()
            raise
        return self._project_update_result(project)

    def complete_research(
        self, *, current_user_id: int, project_id: int
    ) -> dict[str, object]:
        project = self._get_owned_project(
            current_user_id=current_user_id, project_id=project_id
        )
        workflow_state = WorkflowService.research_complete_result(
            project.workflow_state
        )

        try:
            project = self.repository.update_workflow_state(
                project, workflow_state=workflow_state
            )
            self.db.commit()
            self.db.refresh(project)
        except Exception:
            self.db.rollback()
            raise

        return {
            "projectId": project.id,
            "workflowState": project.workflow_state,
            "updatedAt": project.updated_at,
        }

    def delete_project(self, *, current_user_id: int, project_id: int) -> None:
        project = self._get_owned_project(
            current_user_id=current_user_id, project_id=project_id
        )
        try:
            self.repository.soft_delete(project)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _get_owned_project(
        self, *, current_user_id: int, project_id: int
    ) -> CourseProject:
        project = self.repository.get_by_id_and_user(
            project_id=project_id, user_id=current_user_id
        )
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return project

    @staticmethod
    def _project_summary(project: CourseProject) -> dict[str, object]:
        return {
            "projectId": project.id,
            "title": project.title,
            "topic": project.topic,
            "grade": project.grade,
            "classHours": project.class_hours,
            "studentLevel": project.student_level,
            "workflowState": project.workflow_state,
            "updatedAt": project.updated_at,
        }

    @classmethod
    def _project_detail(cls, project: CourseProject) -> dict[str, object]:
        return {
            **cls._project_summary(project),
            "projectType": project.project_type,
            "classHours": project.class_hours,
            "studentLevel": project.student_level,
            "aiAccessMode": project.ai_access_mode,
            "devices": project.devices_json,
            "constraints": project.constraints_json,
            "additionalRequirements": project.additional_requirements,
            "staleSections": project.stale_sections_json or [],
            "createdAt": project.created_at,
        }

    @staticmethod
    def _project_update_result(project: CourseProject) -> dict[str, object]:
        return {
            "projectId": project.id,
            "title": project.title,
            "topic": project.topic,
            "projectType": project.project_type,
            "workflowState": project.workflow_state,
            "staleSections": project.stale_sections_json or [],
            "updatedAt": project.updated_at,
        }

    @staticmethod
    def _project_context_result(project: CourseProject) -> dict[str, object]:
        """Return exactly the fields declared by ProjectContextResponse."""
        return {
            "projectId": project.id,
            "workflowState": project.workflow_state,
            "staleSections": project.stale_sections_json or [],
            "updatedAt": project.updated_at,
        }
