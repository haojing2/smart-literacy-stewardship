from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.assistants.base import ResearchAssistantProvider
from app.assistants.factory import build_research_assistant_provider
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.project import (
    BasicProjectContextRequest,
    PaginationResponse,
    ProjectContextRequest,
    ProjectContextResponse,
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectDetailResponse,
    ProjectDeleteResponse,
    ProjectUpdateRequest,
    ProjectUpdateResponse,
    ProjectWorkflowTransitionResponse,
)
from app.services.project_service import ProjectNotFoundError, ProjectService
from app.services.course_context_service import (
    ContextDiagnosisMissingError,
    ContextIncompleteError,
    CourseContextService,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def get_research_assistant_provider() -> ResearchAssistantProvider:
    return build_research_assistant_provider()


@router.get("")
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1, le=100),
    grade: int | None = Query(None, gt=0),
    keyword: str | None = Query(None),
    sort: str | None = Query(None),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = ProjectService(db).list_projects(
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        grade=grade,
        keyword=keyword,
        sort=sort,
    )
    data = PaginationResponse.model_validate(
        {**result, "page": page, "pageSize": page_size}
    ).model_dump(by_alias=True, mode="json")
    return success_response(data)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = ProjectService(db).create_project(
        current_user_id=current_user.id,
        title=payload.title,
        topic=payload.topic,
        project_type=payload.project_type.value,
    )
    data = ProjectCreateResponse.model_validate(result).model_dump(
        by_alias=True, mode="json"
    )
    return success_response(data)


@router.get("/{project_id}")
def get_project(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ProjectService(db).get_project(
            current_user_id=current_user.id, project_id=project_id
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    data = ProjectDetailResponse.model_validate(result).model_dump(
        by_alias=True, mode="json"
    )
    return success_response(data)


@router.put("/{project_id}/context")
def save_context(
    project_id: int,
    payload: BasicProjectContextRequest | ProjectContextRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if isinstance(payload, BasicProjectContextRequest):
            result = ProjectService(db).save_context(
                current_user_id=current_user.id,
                project_id=project_id,
                grade=payload.grade,
                class_hours=payload.class_hours,
                student_level=payload.student_level.value,
                ai_access_mode=payload.ai_access_mode.value,
                devices=payload.devices,
                constraints=payload.constraints,
                additional_requirements=payload.additional_requirements,
            )
        else:
            result = CourseContextService(db).save_context(
                current_user_id=current_user.id,
                project_id=project_id,
                payload=payload,
            )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    data = ProjectContextResponse.model_validate(result).model_dump(
        by_alias=True, mode="json"
    )
    return success_response(data)


@router.post("/{project_id}/context/diagnose")
async def diagnose_context(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAssistantProvider = Depends(get_research_assistant_provider),
):
    try:
        result = await CourseContextService(db).diagnose_context(
            current_user_id=current_user.id,
            project_id=project_id,
            provider=provider,
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    except ContextIncompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "WORKFLOW_ERROR", "message": str(exc)},
        ) from None
    return success_response(result.model_dump(by_alias=True, mode="json"))


@router.post("/{project_id}/context/confirm")
def confirm_context(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = CourseContextService(db).confirm_context(
            current_user_id=current_user.id, project_id=project_id
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    except ContextIncompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "WORKFLOW_ERROR", "message": str(exc)},
        ) from None
    except (ContextDiagnosisMissingError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "WORKFLOW_ERROR", "message": str(exc)},
        ) from None
    data = ProjectContextResponse.model_validate(result).model_dump(by_alias=True, mode="json")
    return success_response(data)


@router.post("/{project_id}/research/complete")
def complete_project_research(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ProjectService(db).complete_research(
            current_user_id=current_user.id, project_id=project_id
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40916, "message": str(exc)},
        ) from None

    data = ProjectWorkflowTransitionResponse.model_validate(result).model_dump(
        by_alias=True, mode="json"
    )
    return success_response(data)


@router.patch("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdateRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ProjectService(db).update_project(
            current_user_id=current_user.id,
            project_id=project_id,
            title=payload.title,
            topic=payload.topic,
            project_type=(
                payload.project_type.value if payload.project_type is not None else None
            ),
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    data = ProjectUpdateResponse.model_validate(result).model_dump(
        by_alias=True, mode="json"
    )
    return success_response(data)


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        ProjectService(db).delete_project(
            current_user_id=current_user.id, project_id=project_id
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    data = ProjectDeleteResponse(project_id=project_id, deleted=True).model_dump(
        by_alias=True, mode="json"
    )
    return success_response(data)
