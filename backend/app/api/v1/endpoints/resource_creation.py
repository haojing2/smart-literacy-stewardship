from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.assistants.base import ResearchAssistantProvider
from app.assistants.factory import build_research_assistant_provider
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.resource_creation import (
    ResourceCreationJobCreateRequest,
    ResourceCreationJobUpdateRequest,
    ResourceReviewRequest,
    ResourceSuggestionCreateRequest,
    ResourceSuggestionReviseRequest,
    ResourceTransformRequest,
    TeachingResourceVersionCreateRequest,
)
from app.services.project_service import ProjectNotFoundError
from app.services.resource_creation_service import (
    CourseDesignIncompleteError,
    ResourceCreationJobNotFoundError,
    ResourceCreationService,
    ResourceSuggestionDecisionError,
    ResourceSuggestionNotFoundError,
    TeachingResourceNotFoundError,
    TeachingResourceVersionNotFoundError,
)


router = APIRouter(prefix="/api/v1/projects", tags=["resource-creation"])


def get_research_assistant_provider() -> ResearchAssistantProvider:
    return build_research_assistant_provider()


def _project_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": 40401, "message": "Project was not found"},
    )


def _job_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": 40420, "message": "Resource creation job was not found"},
    )


def _course_design_incomplete() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40920, "message": "Course design is incomplete"},
    )


def _resource_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40421, "message": "Teaching resource was not found"})


def _version_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40422, "message": "Teaching resource version was not found"})


def _suggestion_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40423, "message": "Resource suggestion was not found"})


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": 42202, "message": message})


@router.get("/{project_id}/resource-creation")
def get_resource_creation_state(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).get_state(
            current_user_id=current_user.id, project_id=project_id
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    return success_response(result)


@router.post("/{project_id}/resource-creation/jobs", status_code=status.HTTP_201_CREATED)
def create_resource_creation_job(
    project_id: int,
    payload: ResourceCreationJobCreateRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).create_job(
            current_user_id=current_user.id, project_id=project_id, payload=payload
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": 42202, "message": str(exc)}) from None
    return success_response(result)


@router.patch("/{project_id}/resource-creation/jobs/{job_id}")
def update_resource_creation_job(
    project_id: int,
    job_id: int,
    payload: ResourceCreationJobUpdateRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).update_job(
            current_user_id=current_user.id, project_id=project_id, job_id=job_id, payload=payload
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except ResourceCreationJobNotFoundError:
        raise _job_not_found() from None
    return success_response(result)


@router.post("/{project_id}/resource-creation/jobs/{job_id}/recommend-settings")
def recommend_settings(
    project_id: int,
    job_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).recommend_settings(
            current_user_id=current_user.id, project_id=project_id, job_id=job_id
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except ResourceCreationJobNotFoundError:
        raise _job_not_found() from None
    return success_response(result)


@router.post("/{project_id}/resource-creation/jobs/{job_id}/generate")
async def generate_resources(
    project_id: int,
    job_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAssistantProvider = Depends(get_research_assistant_provider),
):
    try:
        result = await ResourceCreationService(db).generate(
            current_user_id=current_user.id, project_id=project_id, job_id=job_id, provider=provider
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except ResourceCreationJobNotFoundError:
        raise _job_not_found() from None
    except CourseDesignIncompleteError:
        raise _course_design_incomplete() from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": 42202, "message": str(exc)}) from None
    return success_response(result)


@router.post("/{project_id}/resource-creation/jobs/{job_id}/regenerate")
async def regenerate_resources(
    project_id: int,
    job_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAssistantProvider = Depends(get_research_assistant_provider),
):
    try:
        result = await ResourceCreationService(db).generate(
            current_user_id=current_user.id, project_id=project_id, job_id=job_id,
            provider=provider, regenerate=True,
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except ResourceCreationJobNotFoundError:
        raise _job_not_found() from None
    except CourseDesignIncompleteError:
        raise _course_design_incomplete() from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": 42202, "message": str(exc)}) from None
    return success_response(result)


@router.get("/{project_id}/teaching-resources/{resource_id}")
def get_teaching_resource(
    project_id: int, resource_id: int,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).get_resource_detail(
            current_user_id=current_user.id, project_id=project_id, resource_id=resource_id
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except TeachingResourceNotFoundError:
        raise _resource_not_found() from None
    return success_response(result)


@router.post("/{project_id}/teaching-resources/{resource_id}/versions", status_code=status.HTTP_201_CREATED)
def save_teacher_resource_version(
    project_id: int, resource_id: int, payload: TeachingResourceVersionCreateRequest,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).create_teacher_version(
            current_user_id=current_user.id, project_id=project_id, resource_id=resource_id, payload=payload
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except TeachingResourceNotFoundError:
        raise _resource_not_found() from None
    return success_response(result)


@router.get("/{project_id}/teaching-resources/{resource_id}/versions")
def get_teaching_resource_versions(
    project_id: int, resource_id: int,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).list_resource_versions(
            current_user_id=current_user.id, project_id=project_id, resource_id=resource_id
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except TeachingResourceNotFoundError:
        raise _resource_not_found() from None
    return success_response(result)


@router.post("/{project_id}/teaching-resources/{resource_id}/versions/{version_id}/restore")
def restore_teaching_resource_version(
    project_id: int, resource_id: int, version_id: int,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).restore_version(
            current_user_id=current_user.id, project_id=project_id, resource_id=resource_id, version_id=version_id
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except TeachingResourceNotFoundError:
        raise _resource_not_found() from None
    except TeachingResourceVersionNotFoundError:
        raise _version_not_found() from None
    return success_response(result)


@router.post("/{project_id}/teaching-resources/{resource_id}/transform")
def transform_teaching_resource(
    project_id: int, resource_id: int, payload: ResourceTransformRequest,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).transform_resource(
            current_user_id=current_user.id, project_id=project_id, resource_id=resource_id, payload=payload
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except TeachingResourceNotFoundError:
        raise _resource_not_found() from None
    except TeachingResourceVersionNotFoundError:
        raise _version_not_found() from None
    except ValueError as exc:
        raise _unprocessable(str(exc)) from None
    return success_response(result)


@router.post("/{project_id}/teaching-resources/{resource_id}/review", status_code=status.HTTP_201_CREATED)
def review_teaching_resource(
    project_id: int, resource_id: int, payload: ResourceReviewRequest | None = None,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).review_resource(
            current_user_id=current_user.id, project_id=project_id, resource_id=resource_id,
            payload=payload or ResourceReviewRequest(),
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except TeachingResourceNotFoundError:
        raise _resource_not_found() from None
    except TeachingResourceVersionNotFoundError:
        raise _version_not_found() from None
    return success_response(result)


@router.post("/{project_id}/teaching-resources/{resource_id}/suggestions", status_code=status.HTTP_201_CREATED)
def create_resource_suggestion(
    project_id: int, resource_id: int, payload: ResourceSuggestionCreateRequest,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    try:
        result = ResourceCreationService(db).create_suggestion(
            current_user_id=current_user.id, project_id=project_id, resource_id=resource_id, payload=payload
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except TeachingResourceNotFoundError:
        raise _resource_not_found() from None
    except TeachingResourceVersionNotFoundError:
        raise _version_not_found() from None
    except (ResourceSuggestionNotFoundError, ValueError) as exc:
        raise _unprocessable(str(exc)) from None
    return success_response(result)


@router.post("/{project_id}/resource-suggestions/{suggestion_id}/accept")
def accept_resource_suggestion(
    project_id: int, suggestion_id: int,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return _decide_resource_suggestion(project_id, suggestion_id, "ACCEPTED", None, current_user, db)


@router.post("/{project_id}/resource-suggestions/{suggestion_id}/revise")
def revise_resource_suggestion(
    project_id: int, suggestion_id: int, payload: ResourceSuggestionReviseRequest,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    if payload.status != "REVISED":
        raise _unprocessable("Suggestion revise requires status REVISED")
    return _decide_resource_suggestion(project_id, suggestion_id, "REVISED", payload.teacher_revision, current_user, db)


@router.post("/{project_id}/resource-suggestions/{suggestion_id}/reject")
def reject_resource_suggestion(
    project_id: int, suggestion_id: int,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return _decide_resource_suggestion(project_id, suggestion_id, "REJECTED", None, current_user, db)


def _decide_resource_suggestion(
    project_id: int, suggestion_id: int, decision: str, revision: str | None,
    current_user: SysUser, db: Session,
):
    try:
        result = ResourceCreationService(db).decide_suggestion(
            current_user_id=current_user.id, project_id=project_id,
            suggestion_id=suggestion_id, decision=decision, revision=revision,
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except TeachingResourceNotFoundError:
        raise _resource_not_found() from None
    except ResourceSuggestionNotFoundError:
        raise _suggestion_not_found() from None
    except (ResourceSuggestionDecisionError, TeachingResourceVersionNotFoundError, ValueError) as exc:
        raise _unprocessable(str(exc)) from None
    return success_response(result)
