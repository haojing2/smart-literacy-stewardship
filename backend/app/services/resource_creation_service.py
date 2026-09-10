from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistants.base import ResearchAssistantProvider
from app.models.course_design import (
    ProjectActivity,
    ProjectAssessment,
    ProjectObjective,
    ProjectPedagogy,
)
from app.models.course_project import CourseProject
from app.models.resource_creation import (
    ResourceCreationJob,
    ResourceAiSuggestion,
    TeachingResource,
    TeachingResourceVersion,
)
from app.repositories.resource_creation_repository import ResourceCreationRepository
from app.schemas.resource_creation import (
    ResourceCreationJobCreateRequest,
    ResourceCreationJobUpdateRequest,
    ResourceReviewRequest,
    ResourceSuggestionCreateRequest,
    ResourceSuggestionReviseRequest,
    ResourceTransformRequest,
    TeachingResourceGenerationResult,
    TeachingResourceVersionCreateRequest,
    ResourceType,
)
from app.assistants.prompts.resource_creation import validate_generated_resource
from app.services.resource_generation_context_service import ResourceGenerationContextService
from app.services.project_service import ProjectNotFoundError


logger = logging.getLogger(__name__)


class ResourceCreationJobNotFoundError(LookupError):
    pass


class CourseDesignIncompleteError(ValueError):
    pass


class TeachingResourceNotFoundError(LookupError):
    pass


class TeachingResourceVersionNotFoundError(LookupError):
    pass


class ResourceSuggestionNotFoundError(LookupError):
    pass


class ResourceSuggestionDecisionError(ValueError):
    pass


class ResourceCreationService:
    """Mode A orchestration backed exclusively by persisted course design."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ResourceCreationRepository(db)

    def get_state(self, *, current_user_id: int, project_id: int) -> dict[str, object]:
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        job = self.repository.get_latest_job(
            project_id=project_id, current_user_id=current_user_id
        )
        resources = self.repository.list_latest_project_resources_by_type(
            project_id=project_id, current_user_id=current_user_id
        )
        return {
            "job": self._job_view(job) if job is not None else None,
            "resources": [self._resource_view(item) for item in resources],
        }

    def create_job(
        self,
        *,
        current_user_id: int,
        project_id: int,
        payload: ResourceCreationJobCreateRequest,
    ) -> dict[str, object]:
        if payload.project_id != project_id:
            raise ValueError("Project ID does not match the request path")
        try:
            job = self.repository.create_job(
                current_user_id=current_user_id,
                project_id=project_id,
                mode=payload.mode,
                selected_types_json=[item.value for item in payload.selected_types],
                common_settings_json=payload.common_settings,
                resource_settings_json=payload.resource_settings,
            )
            if job is None:
                raise ProjectNotFoundError("Project was not found for the current user")
            self.db.commit()
            self.db.refresh(job)
        except Exception as exc:
            self.db.rollback()
            logger.exception(
                "Resource job save failed operation=create exception_type=%s project_id=%s",
                type(exc).__name__, project_id,
            )
            raise
        return {"job": self._job_view(job)}

    def update_job(
        self,
        *,
        current_user_id: int,
        project_id: int,
        job_id: int,
        payload: ResourceCreationJobUpdateRequest,
    ) -> dict[str, object]:
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        values = payload.model_dump(exclude_unset=True, by_alias=False)
        if "selected_types" in values:
            values["selected_types_json"] = [item.value for item in values.pop("selected_types")]
        if "common_settings" in values:
            values["common_settings_json"] = values.pop("common_settings")
        if "resource_settings" in values:
            values["resource_settings_json"] = values.pop("resource_settings")
        try:
            job = self.repository.update_job(
                job_id=job_id, current_user_id=current_user_id, values=values
            )
            if job is None or job.project_id != project_id:
                raise ResourceCreationJobNotFoundError("Resource creation job was not found")
            self.db.commit()
            self.db.refresh(job)
        except Exception as exc:
            self.db.rollback()
            logger.exception(
                "Resource job save failed operation=update exception_type=%s project_id=%s job_id=%s",
                type(exc).__name__, project_id, job_id,
            )
            raise
        return {"job": self._job_view(job)}

    def recommend_settings(
        self, *, current_user_id: int, project_id: int, job_id: int
    ) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        job = self._owned_job(job_id=job_id, project_id=project_id, current_user_id=current_user_id)
        recommendations = {
            "grade": project.grade,
            "lessonMinutes": project.lesson_minutes,
            "studentLevel": project.student_level,
            "devices": project.devices_json or [],
            "resourceStyle": "CLASSROOM_READY",
        }
        job = self.repository.update_job(
            job_id=job.id,
            current_user_id=current_user_id,
            values={"common_settings_json": recommendations, "current_step": 2},
        )
        if job is None:
            raise ResourceCreationJobNotFoundError("Resource creation job was not found")
        try:
            self.db.commit()
            self.db.refresh(job)
        except Exception:
            self.db.rollback()
            raise
        return {"job": self._job_view(job), "recommendations": recommendations}

    async def generate(
        self,
        *,
        current_user_id: int,
        project_id: int,
        job_id: int,
        provider: ResearchAssistantProvider,
        regenerate: bool = False,
    ) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        job = self._owned_job(job_id=job_id, project_id=project_id, current_user_id=current_user_id)
        selected_types = list(job.selected_types_json or [])
        if not selected_types:
            raise ValueError("At least one resource type must be selected")

        try:
            resources: list[TeachingResource] = []
            project_resources = {
                item.resource_type: item
                for item in self.repository.list_latest_project_resources_by_type(
                    project_id=project_id, current_user_id=current_user_id
                )
            }
            job_resources = {
                item.resource_type: item
                for item in self.repository.list_resources(
                    project_id=project_id, current_user_id=current_user_id, job_id=job.id
                )
            }
            for resource_type in selected_types:
                resource = project_resources.get(resource_type)
                if resource is not None and not regenerate:
                    # A persisted version is the source of truth. Ordinary generation is
                    # deliberately idempotent and must never replace teacher/AI edits.
                    resources.append(resource)
                    continue
                if ResourceType(resource_type) == ResourceType.PPT:
                    # PPT is intentionally reserved for its dedicated model/API.
                    if resource is not None:
                        resources.append(resource)
                    continue
                failure_stage = "prompt_build"
                provider_request = ResourceGenerationContextService(self.db).build(
                    project_id=project_id,
                    current_user_id=current_user_id,
                    resource_type=resource_type,
                    common_settings=job.common_settings_json,
                    resource_settings=job.resource_settings_json,
                )
                failure_stage = "provider_call"
                provider_result = await provider.generate_teaching_resource(provider_request)
                failure_stage = "schema_validation"
                generated_result = TeachingResourceGenerationResult.model_validate(
                    provider_result
                )
                validate_generated_resource(provider_request.resource_type, generated_result.content, provider_request)
                generated_result.content.metadata.update({
                    "resourceType": provider_request.resource_type.value,
                    "provider": provider.provider_name,
                    "projectId": project_id,
                    "courseDesignBased": True,
                    "researchEvidenceCount": len(provider_request.research_evidence),
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                })
                content = generated_result.content.model_dump(mode="json", by_alias=True)
                failure_stage = "database_save"
                resource = resource or job_resources.get(resource_type)
                if resource is None:
                    resource = self.repository.create_resource(
                        job_id=job.id,
                        current_user_id=current_user_id,
                        resource_type=resource_type,
                        title=generated_result.title,
                        settings_json=provider_request.resource_settings,
                    )
                    if resource is None:
                        raise ResourceCreationJobNotFoundError("Resource creation job was not found")
                    version_no = 1
                else:
                    version_no = resource.current_version_no + 1
                    resource.current_version_no = version_no
                    resource.title = generated_result.title
                    resource.status = "READY"
                version = self.repository.create_version(
                    resource_id=resource.id,
                    current_user_id=current_user_id,
                    version_no=version_no,
                    content_json=content,
                    content_html=None,
                    change_source="AI",
                    change_summary=generated_result.change_summary or (
                        "Regenerated by Mock AI" if regenerate else "Generated by Mock AI"
                    ),
                    created_by=current_user_id,
                )
                if version is None:
                    raise ResourceCreationJobNotFoundError("Teaching resource was not found")
                resources.append(resource)

            job.status = "READY"
            job.current_step = 3
            job.error_message = None
            self.db.commit()
            for item in resources:
                self.db.refresh(item)
            self.db.refresh(job)
        except Exception as exc:
            self.db.rollback()
            logger.exception(
                "Teaching resource generation failed stage=%s exception_type=%s project_id=%s job_id=%s resource_type=%s",
                locals().get("failure_stage", "database_save"), type(exc).__name__, project_id, job_id,
                locals().get("resource_type"),
            )
            raise
        return {
            "job": self._job_view(job),
            "resources": [self._resource_view(item) for item in resources],
        }

    def get_resource_detail(
        self, *, current_user_id: int, project_id: int, resource_id: int
    ) -> dict[str, object]:
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        resource = self._owned_resource(
            resource_id=resource_id, project_id=project_id, current_user_id=current_user_id
        )
        version = self.repository.get_current_version(
            resource_id=resource.id, current_user_id=current_user_id
        )
        suggestions = self.repository.list_suggestions(
            resource_id=resource.id, current_user_id=current_user_id
        )
        return {
            "resource": self._resource_view(resource),
            "currentVersion": self._version_view(version) if version else None,
            "suggestions": [self._suggestion_view(item) for item in suggestions],
        }

    def create_teacher_version(
        self, *, current_user_id: int, project_id: int, resource_id: int,
        payload: TeachingResourceVersionCreateRequest,
    ) -> dict[str, object]:
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        resource = self._owned_resource(
            resource_id=resource_id, project_id=project_id, current_user_id=current_user_id
        )
        return self._append_version(
            resource=resource, current_user_id=current_user_id,
            content=payload.content.model_dump(mode="json", by_alias=True),
            content_html=payload.content_html, change_source="TEACHER",
            change_summary=payload.change_summary or "Edited by teacher",
        )

    def list_resource_versions(
        self, *, current_user_id: int, project_id: int, resource_id: int
    ) -> dict[str, object]:
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        resource = self._owned_resource(
            resource_id=resource_id, project_id=project_id, current_user_id=current_user_id
        )
        versions = self.repository.list_versions(
            resource_id=resource.id, current_user_id=current_user_id
        )
        return {"resource": self._resource_view(resource), "versions": [self._version_view(item) for item in versions]}

    def restore_version(
        self, *, current_user_id: int, project_id: int, resource_id: int, version_id: int
    ) -> dict[str, object]:
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        resource = self._owned_resource(
            resource_id=resource_id, project_id=project_id, current_user_id=current_user_id
        )
        version = self.repository.get_version(
            resource_id=resource.id, version_id=version_id, current_user_id=current_user_id
        )
        if version is None:
            raise TeachingResourceVersionNotFoundError("Teaching resource version was not found")
        return self._append_version(
            resource=resource, current_user_id=current_user_id, content=version.content_json,
            content_html=version.content_html, change_source="TEACHER",
            change_summary=f"Restored from version {version.version_no}",
        )

    def transform_resource(
        self, *, current_user_id: int, project_id: int, resource_id: int,
        payload: ResourceTransformRequest,
    ) -> dict[str, object]:
        allowed = {"REGENERATE", "SIMPLIFY", "INCREASE_DIFFICULTY", "ADD_SCAFFOLD"}
        if payload.action not in allowed:
            raise ValueError("Unsupported resource transform action")
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        resource = self._owned_resource(
            resource_id=resource_id, project_id=project_id, current_user_id=current_user_id
        )
        current = self.repository.get_current_version(
            resource_id=resource.id, current_user_id=current_user_id
        )
        if current is None:
            raise TeachingResourceVersionNotFoundError("Teaching resource has no current version")
        content = payload.content.model_dump(mode="json", by_alias=True) if payload.content else dict(current.content_json)
        metadata = dict(content.get("metadata") or {}) if isinstance(content, dict) else {}
        metadata.update({"transform": payload.action, "instruction": payload.instruction or "", "provider": "mock"})
        if isinstance(content, dict):
            content["metadata"] = metadata
        return self._append_version(
            resource=resource, current_user_id=current_user_id, content=content,
            content_html=current.content_html, change_source="AI",
            change_summary=f"{payload.action} requested by teacher",
        )

    def review_resource(
        self, *, current_user_id: int, project_id: int, resource_id: int,
        payload: ResourceReviewRequest,
    ) -> dict[str, object]:
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        resource = self._owned_resource(
            resource_id=resource_id, project_id=project_id, current_user_id=current_user_id
        )
        current = self.repository.get_current_version(resource_id=resource.id, current_user_id=current_user_id)
        if current is None:
            raise TeachingResourceVersionNotFoundError("Teaching resource has no current version")
        suggestion = self._create_pending_suggestion(
            resource=resource, version=current, current_user_id=current_user_id,
            suggestion_type="AI_REVIEW", target_block_key=payload.target_block_key,
            issue="Mock AI review recommends improving instructional clarity.",
            reason=payload.instruction or "Review requested by teacher.",
            proposed_content=current.content_json,
        )
        return {"suggestion": self._suggestion_view(suggestion)}

    def create_suggestion(
        self, *, current_user_id: int, project_id: int, resource_id: int,
        payload: ResourceSuggestionCreateRequest,
    ) -> dict[str, object]:
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        resource = self._owned_resource(resource_id=resource_id, project_id=project_id, current_user_id=current_user_id)
        if payload.resource_id != resource.id:
            raise ValueError("Resource ID does not match the request path")
        version = self.repository.get_version(resource_id=resource.id, version_id=payload.base_version_id, current_user_id=current_user_id)
        if version is None:
            raise TeachingResourceVersionNotFoundError("Teaching resource version was not found")
        suggestion = self.repository.create_suggestion(
            resource_id=resource.id, base_version_id=version.id, current_user_id=current_user_id,
            suggestion_type=payload.suggestion_type, target_block_key=payload.target_block_key,
            issue=payload.issue, reason=payload.reason, user_request=payload.user_request,
            suggested_content=payload.suggested_content, metadata_json=payload.metadata,
        )
        if suggestion is None:
            raise ResourceSuggestionNotFoundError("Resource suggestion could not be created")
        self._commit_refresh(suggestion)
        return {"suggestion": self._suggestion_view(suggestion)}

    def decide_suggestion(
        self, *, current_user_id: int, project_id: int, suggestion_id: int,
        decision: str, revision: str | None = None,
    ) -> dict[str, object]:
        self._owned_project(current_user_id=current_user_id, project_id=project_id)
        suggestion = self.repository.get_suggestion(suggestion_id=suggestion_id, current_user_id=current_user_id, for_update=True)
        if suggestion is None:
            raise ResourceSuggestionNotFoundError("Resource suggestion was not found")
        if suggestion.status != "PENDING":
            raise ResourceSuggestionDecisionError("Resource suggestion has already been decided")
        resource = self._owned_resource(resource_id=suggestion.resource_id, project_id=project_id, current_user_id=current_user_id)
        if decision == "REJECTED":
            updated = self.repository.update_suggestion(
                suggestion_id=suggestion.id, current_user_id=current_user_id,
                values={"status": "REJECTED", "decided_at": datetime.now()},
            )
            if updated is None:
                raise ResourceSuggestionNotFoundError("Resource suggestion was not found")
            self._commit_refresh(updated)
            return {"suggestion": self._suggestion_view(updated), "version": None}
        content = self._suggestion_content(suggestion, revision)
        result = self._append_version(
            resource=resource, current_user_id=current_user_id, content=content,
            content_html=None, change_source="AI_ACCEPTED",
            change_summary="AI suggestion accepted" if decision == "ACCEPTED" else "AI suggestion revised by teacher",
            commit=False,
        )
        updated = self.repository.update_suggestion(
            suggestion_id=suggestion.id, current_user_id=current_user_id,
            values={"status": decision, "teacher_revision": revision, "decided_at": datetime.now()},
        )
        if updated is None:
            self.db.rollback()
            raise ResourceSuggestionNotFoundError("Resource suggestion was not found")
        self._commit_refresh(updated)
        return {"suggestion": self._suggestion_view(updated), "version": result["version"]}

    def _append_version(
        self,
        *,
        resource: TeachingResource,
        current_user_id: int,
        content: dict[str, Any] | list[Any],
        content_html: str | None,
        change_source: str,
        change_summary: str | None,
        commit: bool = True,
    ) -> dict[str, object]:
        """Append only: no operation mutates an existing resource version."""
        try:
            next_version_no = resource.current_version_no + 1
            version = self.repository.create_version(
                resource_id=resource.id,
                current_user_id=current_user_id,
                version_no=next_version_no,
                content_json=content,
                content_html=content_html,
                change_source=change_source,
                change_summary=change_summary,
                created_by=current_user_id,
            )
            if version is None:
                raise TeachingResourceNotFoundError("Teaching resource was not found")
            resource.current_version_no = next_version_no
            if commit:
                self.db.commit()
                self.db.refresh(resource)
                self.db.refresh(version)
        except Exception:
            if commit:
                self.db.rollback()
            raise
        return {"resource": self._resource_view(resource), "version": self._version_view(version)}

    def _create_pending_suggestion(
        self,
        *,
        resource: TeachingResource,
        version: TeachingResourceVersion,
        current_user_id: int,
        suggestion_type: str,
        target_block_key: str | None,
        issue: str | None,
        reason: str | None,
        proposed_content: dict[str, Any] | list[Any],
    ) -> ResourceAiSuggestion:
        suggestion = self.repository.create_suggestion(
            resource_id=resource.id,
            base_version_id=version.id,
            current_user_id=current_user_id,
            suggestion_type=suggestion_type,
            target_block_key=target_block_key,
            issue=issue,
            reason=reason,
            suggested_content="Mock AI suggestion; teacher approval is required.",
            metadata_json={"proposedContent": proposed_content},
        )
        if suggestion is None:
            raise ResourceSuggestionNotFoundError("Resource suggestion could not be created")
        self._commit_refresh(suggestion)
        return suggestion

    def _suggestion_content(
        self, suggestion: ResourceAiSuggestion, revision: str | None
    ) -> dict[str, Any] | list[Any]:
        if revision:
            try:
                parsed = json.loads(revision)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError:
                pass
        proposed = (suggestion.metadata_json or {}).get("proposedContent")
        if isinstance(proposed, (dict, list)):
            return proposed
        base = self.db.get(TeachingResourceVersion, suggestion.base_version_id)
        if base is None:
            raise TeachingResourceVersionNotFoundError("Teaching resource version was not found")
        content = dict(base.content_json) if isinstance(base.content_json, dict) else list(base.content_json)
        if revision and isinstance(content, dict):
            content["teacherRevision"] = revision
        return content

    def _commit_refresh(self, item: Any) -> None:
        try:
            self.db.commit()
            self.db.refresh(item)
        except Exception:
            self.db.rollback()
            raise

    def _owned_project(self, *, current_user_id: int, project_id: int) -> CourseProject:
        project = self.repository._get_owned_project(
            project_id=project_id, current_user_id=current_user_id
        )
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return project

    def _owned_job(
        self, *, job_id: int, project_id: int, current_user_id: int
    ) -> ResourceCreationJob:
        job = self.repository.get_job(job_id=job_id, current_user_id=current_user_id)
        if job is None or job.project_id != project_id:
            raise ResourceCreationJobNotFoundError("Resource creation job was not found")
        return job

    def _owned_resource(
        self, *, resource_id: int, project_id: int, current_user_id: int
    ) -> TeachingResource:
        resource = self.repository.get_resource(
            resource_id=resource_id, current_user_id=current_user_id
        )
        if resource is None or resource.project_id != project_id:
            raise TeachingResourceNotFoundError("Teaching resource was not found")
        return resource

    def _course_design_basis(self, project: CourseProject) -> dict[str, list[dict[str, Any]] | dict[str, Any]]:
        objectives = list(self.db.scalars(
            select(ProjectObjective).where(
                ProjectObjective.project_id == project.id,
                ProjectObjective.confirmed.is_(True),
            ).order_by(ProjectObjective.sequence_no)
        ).all())
        pedagogy = self.db.scalar(
            select(ProjectPedagogy).where(
                ProjectPedagogy.project_id == project.id,
                ProjectPedagogy.confirmed.is_(True),
            ).order_by(ProjectPedagogy.id.desc()).limit(1)
        )
        assessments = list(self.db.scalars(
            select(ProjectAssessment).where(
                ProjectAssessment.project_id == project.id,
                ProjectAssessment.confirmed.is_(True),
            ).order_by(ProjectAssessment.id)
        ).all())
        activities = list(self.db.scalars(
            select(ProjectActivity).where(ProjectActivity.project_id == project.id)
            .order_by(ProjectActivity.sequence_no)
        ).all())
        if not objectives or pedagogy is None or not assessments or not activities:
            raise CourseDesignIncompleteError("Course design is incomplete")
        return {
            "objectives": [{"id": item.id, "content": item.content} for item in objectives],
            "pedagogy": {
                "id": pedagogy.id,
                "primaryMethodId": pedagogy.primary_method_id,
                "customName": pedagogy.custom_name,
                "description": pedagogy.custom_description or pedagogy.rationale or "",
            },
            "assessments": [{"objectiveId": item.objective_id, "task": item.task_content} for item in assessments],
            "activities": [{"id": item.id, "name": item.name, "coreTask": item.core_task or ""} for item in activities],
        }

    @staticmethod
    def _provider_request(
        project: CourseProject, basis: dict[str, Any], resource_type: str
    ) -> dict[str, object]:
        return {
            "resourceType": resource_type,
            "project": {"title": project.title, "topic": project.topic, "grade": project.grade},
            "objectives": basis["objectives"],
            "pedagogy": basis["pedagogy"],
            "assessments": basis["assessments"],
            "activities": basis["activities"],
        }

    @staticmethod
    def _job_view(job: ResourceCreationJob) -> dict[str, object]:
        return {
            "jobId": job.id, "projectId": job.project_id, "userId": job.user_id,
            "mode": job.mode, "currentStep": job.current_step,
            "selectedTypes": job.selected_types_json or [],
            "commonSettings": job.common_settings_json or {},
            "resourceSettings": job.resource_settings_json or {}, "status": job.status,
            "errorMessage": job.error_message, "createdAt": job.created_at,
            "updatedAt": job.updated_at,
        }

    @staticmethod
    def _resource_view(resource: TeachingResource) -> dict[str, object]:
        return {
            "resourceId": resource.id, "jobId": resource.job_id,
            "projectId": resource.project_id, "resourceType": resource.resource_type,
            "title": resource.title, "settings": resource.settings_json or {},
            "status": resource.status, "currentVersionNo": resource.current_version_no,
            "errorMessage": resource.error_message, "createdAt": resource.created_at,
            "updatedAt": resource.updated_at,
        }

    @staticmethod
    def _version_view(version: TeachingResourceVersion) -> dict[str, object]:
        return {
            "versionId": version.id,
            "resourceId": version.resource_id,
            "versionNo": version.version_no,
            "content": version.content_json,
            "contentHtml": version.content_html,
            "changeSource": version.change_source,
            "changeSummary": version.change_summary,
            "createdBy": version.created_by,
            "createdAt": version.created_at,
        }

    @staticmethod
    def _suggestion_view(suggestion: ResourceAiSuggestion) -> dict[str, object]:
        return {
            "suggestionId": suggestion.id,
            "resourceId": suggestion.resource_id,
            "baseVersionId": suggestion.base_version_id,
            "targetBlockKey": suggestion.target_block_key,
            "suggestionType": suggestion.suggestion_type,
            "issue": suggestion.issue,
            "reason": suggestion.reason,
            "userRequest": suggestion.user_request,
            "suggestedContent": suggestion.suggested_content,
            "metadata": suggestion.metadata_json or {},
            "status": suggestion.status,
            "teacherRevision": suggestion.teacher_revision,
            "createdAt": suggestion.created_at,
            "decidedAt": suggestion.decided_at,
        }
