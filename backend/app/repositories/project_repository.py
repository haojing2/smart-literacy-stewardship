from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject


class ProjectRepository:
    """Persistence operations for ``course_project`` only."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_project(
        self,
        *,
        user_id: int,
        title: str,
        topic: str,
        project_type: str,
    ) -> CourseProject:
        project = CourseProject(
            user_id=user_id,
            title=title,
            topic=topic,
            project_type=project_type,
            workflow_state="DRAFT",
            stale_sections_json=[],
        )
        self.db.add(project)
        self.db.flush()
        return project

    def get_by_id_and_user(
        self, *, project_id: int, user_id: int
    ) -> CourseProject | None:
        statement = select(CourseProject).where(
            CourseProject.id == project_id,
            CourseProject.user_id == user_id,
            CourseProject.is_deleted.is_(False),
        )
        return self.db.scalar(statement)

    def list_by_user(
        self,
        *,
        user_id: int,
        page: int,
        page_size: int,
        grade: int | None = None,
        keyword: str | None = None,
        sort: str | None = None,
    ) -> tuple[Sequence[CourseProject], int]:
        filters = [
            CourseProject.user_id == user_id,
            CourseProject.is_deleted.is_(False),
        ]
        if grade is not None:
            filters.append(CourseProject.grade == grade)
        if keyword and (normalized_keyword := keyword.strip()):
            filters.append(CourseProject.title.ilike(f"%{normalized_keyword}%"))

        total = self.db.scalar(
            select(func.count()).select_from(CourseProject).where(*filters)
        ) or 0

        safe_page = max(page, 1)
        safe_page_size = max(page_size, 1)
        statement = (
            select(CourseProject)
            .where(*filters)
            .order_by(self._sort_column(sort))
            .offset((safe_page - 1) * safe_page_size)
            .limit(safe_page_size)
        )
        return self.db.scalars(statement).all(), total

    def update_context(
        self,
        project: CourseProject,
        *,
        grade: int | None,
        class_hours: int | None,
        student_level: str | None,
        ai_access_mode: str | None,
        devices_json: list | None,
        constraints_json: list | None,
        additional_requirements: str | None,
        workflow_state: str,
        stale_sections_json: list | None,
    ) -> CourseProject:
        project.grade = grade
        project.class_hours = class_hours
        project.student_level = student_level
        project.ai_access_mode = ai_access_mode
        project.devices_json = devices_json
        project.constraints_json = constraints_json
        project.additional_requirements = additional_requirements
        project.workflow_state = workflow_state
        project.stale_sections_json = stale_sections_json
        self.db.flush()
        return project

    def save_course_design_context(
        self,
        project: CourseProject,
        *,
        grade: int,
        topic: str,
        lesson_minutes: int,
        class_size: int,
        student_experience: str,
        device_condition: str,
        additional_requirements: str,
        workflow_state: str,
        stale_sections_json: list | None,
    ) -> CourseProject:
        project.grade = grade
        project.topic = topic
        project.lesson_minutes = lesson_minutes
        project.class_size = class_size
        project.student_experience = student_experience
        project.devices_json = [device_condition]
        project.additional_requirements = additional_requirements
        project.context_diagnosis_json = None
        project.workflow_state = workflow_state
        project.stale_sections_json = stale_sections_json
        self.db.flush()
        return project

    def update_basic_info(
        self,
        project: CourseProject,
        *,
        title: str,
        topic: str,
        project_type: str,
    ) -> CourseProject:
        project.title = title
        project.topic = topic
        project.project_type = project_type
        self.db.flush()
        return project

    def update_workflow_state(
        self, project: CourseProject, *, workflow_state: str
    ) -> CourseProject:
        project.workflow_state = workflow_state
        self.db.flush()
        return project

    def soft_delete(self, project: CourseProject) -> None:
        project.is_deleted = True
        project.deleted_at = datetime.now()
        self.db.flush()

    @staticmethod
    def _sort_column(sort: str | None):
        sort_columns = {
            "updated_at_asc": asc(CourseProject.updated_at),
            "title_asc": asc(CourseProject.title),
            "title_desc": desc(CourseProject.title),
        }
        return sort_columns.get(sort or "", desc(CourseProject.updated_at))
