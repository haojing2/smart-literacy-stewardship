from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.assistants.base import ResearchAssistantProvider
from app.assistants.factory import build_research_assistant_provider
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.services.course_quality_service import (
    CourseQualityApplyError,
    CourseQualityCheckNotFoundError,
    CourseQualityService,
    CourseQualityWorkflowError,
)
from app.services.project_service import ProjectNotFoundError


router = APIRouter(prefix="/api/v1/projects", tags=["course-design-quality"])


def get_research_assistant_provider() -> ResearchAssistantProvider:
    return build_research_assistant_provider()


def _project_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": 40401, "message": "Project was not found"},
    )


@router.post("/{project_id}/quality-check")
async def run_quality_check(
    project_id: int, current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAssistantProvider = Depends(get_research_assistant_provider),
):
    try:
        result = await CourseQualityService(db).run(
            current_user_id=current_user.id, project_id=project_id, provider=provider
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except CourseQualityWorkflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "WORKFLOW_ERROR", "message": str(exc)},
        ) from None
    return success_response(result)


@router.get("/{project_id}/quality-check")
def get_quality_check(
    project_id: int, current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = CourseQualityService(db).get(
            current_user_id=current_user.id, project_id=project_id
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    return success_response(result)


@router.post("/{project_id}/quality-check/{check_id}/apply")
def apply_quality_suggestion(
    project_id: int, check_id: int, current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = CourseQualityService(db).apply(
            current_user_id=current_user.id, project_id=project_id, check_id=check_id
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except CourseQualityCheckNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40412, "message": "Quality check was not found"},
        ) from None
    except CourseQualityApplyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40915, "message": str(exc)},
        ) from None
    return success_response(result)
