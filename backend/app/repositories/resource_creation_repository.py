from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.resource_creation import (
    ResourceAiSuggestion,
    ResourceCreationJob,
    TeachingResource,
    TeachingResourceVersion,
)


class ResourceCreationRepository:
    """Persistence for Mode A resource creation, always scoped to project owner."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_job(
        self,
        *,
        current_user_id: int,
        project_id: int,
        mode: str = "COURSE_GENERATE",
        selected_types_json: list[str] | None = None,
        common_settings_json: dict[str, Any] | None = None,
        resource_settings_json: dict[str, Any] | None = None,
    ) -> ResourceCreationJob | None:
        if self._get_owned_project(project_id=project_id, current_user_id=current_user_id) is None:
            return None
        job = ResourceCreationJob(
            project_id=project_id,
            user_id=current_user_id,
            mode=mode,
            selected_types_json=selected_types_json,
            common_settings_json=common_settings_json,
            resource_settings_json=resource_settings_json,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get_job(
        self, *, job_id: int, current_user_id: int, for_update: bool = False
    ) -> ResourceCreationJob | None:
        statement = self._owned_job_statement(job_id=job_id, current_user_id=current_user_id)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_latest_job(
        self, *, project_id: int, current_user_id: int
    ) -> ResourceCreationJob | None:
        statement = (
            select(ResourceCreationJob)
            .join(CourseProject, CourseProject.id == ResourceCreationJob.project_id)
            .where(
                ResourceCreationJob.project_id == project_id,
                CourseProject.user_id == current_user_id,
                CourseProject.is_deleted.is_(False),
            )
            .order_by(desc(ResourceCreationJob.updated_at), desc(ResourceCreationJob.id))
            .limit(1)
        )
        return self.db.scalar(statement)

    def update_job(
        self,
        *,
        job_id: int,
        current_user_id: int,
        values: dict[str, Any],
    ) -> ResourceCreationJob | None:
        job = self.get_job(job_id=job_id, current_user_id=current_user_id, for_update=True)
        if job is None:
            return None
        allowed = {
            "current_step",
            "selected_types_json",
            "common_settings_json",
            "resource_settings_json",
            "status",
            "error_message",
        }
        for field, value in values.items():
            if field in allowed:
                setattr(job, field, value)
        self.db.flush()
        return job

    def create_resource(
        self,
        *,
        job_id: int,
        current_user_id: int,
        resource_type: str,
        title: str,
        settings_json: dict[str, Any] | None = None,
        status: str = "READY",
    ) -> TeachingResource | None:
        job = self.get_job(job_id=job_id, current_user_id=current_user_id, for_update=True)
        if job is None:
            return None
        resource = TeachingResource(
            job_id=job.id,
            project_id=job.project_id,
            resource_type=resource_type,
            title=title,
            settings_json=settings_json,
            status=status,
        )
        self.db.add(resource)
        self.db.flush()
        return resource

    def get_resource(
        self, *, resource_id: int, current_user_id: int, for_update: bool = False
    ) -> TeachingResource | None:
        statement = self._owned_resource_statement(
            resource_id=resource_id, current_user_id=current_user_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_resources(
        self, *, project_id: int, current_user_id: int, job_id: int | None = None
    ) -> Sequence[TeachingResource]:
        filters = [
            TeachingResource.project_id == project_id,
            CourseProject.user_id == current_user_id,
            CourseProject.is_deleted.is_(False),
        ]
        if job_id is not None:
            filters.append(TeachingResource.job_id == job_id)
        statement = (
            select(TeachingResource)
            .join(CourseProject, CourseProject.id == TeachingResource.project_id)
            .where(*filters)
            .order_by(TeachingResource.resource_type, TeachingResource.id)
        )
        return self.db.scalars(statement).all()

    def create_version(
        self,
        *,
        resource_id: int,
        current_user_id: int,
        version_no: int,
        content_json: dict[str, Any] | list[Any],
        created_by: int,
        change_source: str,
        content_html: str | None = None,
        change_summary: str | None = None,
    ) -> TeachingResourceVersion | None:
        resource = self.get_resource(
            resource_id=resource_id, current_user_id=current_user_id, for_update=True
        )
        if resource is None or created_by != current_user_id:
            return None
        version = TeachingResourceVersion(
            resource_id=resource.id,
            version_no=version_no,
            content_json=content_json,
            content_html=content_html,
            change_source=change_source,
            change_summary=change_summary,
            created_by=created_by,
        )
        self.db.add(version)
        self.db.flush()
        return version

    def get_current_version(
        self, *, resource_id: int, current_user_id: int
    ) -> TeachingResourceVersion | None:
        if self.get_resource(resource_id=resource_id, current_user_id=current_user_id) is None:
            return None
        return self.db.scalar(
            select(TeachingResourceVersion)
            .where(TeachingResourceVersion.resource_id == resource_id)
            .order_by(desc(TeachingResourceVersion.version_no))
            .limit(1)
        )

    def get_version(
        self, *, resource_id: int, version_id: int, current_user_id: int
    ) -> TeachingResourceVersion | None:
        if self.get_resource(resource_id=resource_id, current_user_id=current_user_id) is None:
            return None
        return self.db.scalar(
            select(TeachingResourceVersion).where(
                TeachingResourceVersion.id == version_id,
                TeachingResourceVersion.resource_id == resource_id,
            )
        )

    def list_versions(
        self, *, resource_id: int, current_user_id: int
    ) -> Sequence[TeachingResourceVersion]:
        if self.get_resource(resource_id=resource_id, current_user_id=current_user_id) is None:
            return []
        return self.db.scalars(
            select(TeachingResourceVersion)
            .where(TeachingResourceVersion.resource_id == resource_id)
            .order_by(desc(TeachingResourceVersion.version_no))
        ).all()

    def list_suggestions(
        self, *, resource_id: int, current_user_id: int
    ) -> Sequence[ResourceAiSuggestion]:
        if self.get_resource(resource_id=resource_id, current_user_id=current_user_id) is None:
            return []
        return self.db.scalars(
            select(ResourceAiSuggestion)
            .where(ResourceAiSuggestion.resource_id == resource_id)
            .order_by(desc(ResourceAiSuggestion.id))
        ).all()

    def create_suggestion(
        self,
        *,
        resource_id: int,
        base_version_id: int,
        current_user_id: int,
        suggestion_type: str,
        target_block_key: str | None = None,
        issue: str | None = None,
        reason: str | None = None,
        user_request: str | None = None,
        suggested_content: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ResourceAiSuggestion | None:
        resource = self.get_resource(resource_id=resource_id, current_user_id=current_user_id)
        if resource is None:
            return None
        version = self.db.get(TeachingResourceVersion, base_version_id)
        if version is None or version.resource_id != resource.id:
            return None
        suggestion = ResourceAiSuggestion(
            resource_id=resource.id,
            base_version_id=version.id,
            target_block_key=target_block_key,
            suggestion_type=suggestion_type,
            issue=issue,
            reason=reason,
            user_request=user_request,
            suggested_content=suggested_content,
            metadata_json=metadata_json,
        )
        self.db.add(suggestion)
        self.db.flush()
        return suggestion

    def get_suggestion(
        self, *, suggestion_id: int, current_user_id: int, for_update: bool = False
    ) -> ResourceAiSuggestion | None:
        statement = (
            select(ResourceAiSuggestion)
            .join(TeachingResource, TeachingResource.id == ResourceAiSuggestion.resource_id)
            .join(CourseProject, CourseProject.id == TeachingResource.project_id)
            .where(
                ResourceAiSuggestion.id == suggestion_id,
                CourseProject.user_id == current_user_id,
                CourseProject.is_deleted.is_(False),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def update_suggestion(
        self,
        *,
        suggestion_id: int,
        current_user_id: int,
        values: dict[str, Any],
    ) -> ResourceAiSuggestion | None:
        suggestion = self.get_suggestion(
            suggestion_id=suggestion_id, current_user_id=current_user_id, for_update=True
        )
        if suggestion is None:
            return None
        for field, value in values.items():
            if field in {"status", "teacher_revision", "decided_at"}:
                setattr(suggestion, field, value)
        self.db.flush()
        return suggestion

    def _get_owned_project(
        self, *, project_id: int, current_user_id: int
    ) -> CourseProject | None:
        return self.db.scalar(
            select(CourseProject).where(
                CourseProject.id == project_id,
                CourseProject.user_id == current_user_id,
                CourseProject.is_deleted.is_(False),
            )
        )

    @staticmethod
    def _owned_job_statement(*, job_id: int, current_user_id: int):
        return (
            select(ResourceCreationJob)
            .join(CourseProject, CourseProject.id == ResourceCreationJob.project_id)
            .where(
                ResourceCreationJob.id == job_id,
                CourseProject.user_id == current_user_id,
                CourseProject.is_deleted.is_(False),
            )
        )

    @staticmethod
    def _owned_resource_statement(*, resource_id: int, current_user_id: int):
        return (
            select(TeachingResource)
            .join(CourseProject, CourseProject.id == TeachingResource.project_id)
            .where(
                TeachingResource.id == resource_id,
                CourseProject.user_id == current_user_id,
                CourseProject.is_deleted.is_(False),
            )
        )
