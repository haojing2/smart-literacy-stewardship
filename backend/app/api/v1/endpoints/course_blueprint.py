from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.assistants.base import ResearchAssistantProvider
from app.assistants.factory import build_research_assistant_provider
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.course_design import (
    CourseActivityTransformRequest,
    CourseActivityUpdateRequest,
)
from app.services.course_blueprint_service import (
    CourseActivityNotFoundError,
    CourseBlueprintDurationError,
    CourseBlueprintService,
    CourseBlueprintWorkflowError,
)
from app.services.project_service import ProjectNotFoundError


router = APIRouter(prefix="/api/v1/projects", tags=["course-design-blueprint"])


def get_research_assistant_provider() -> ResearchAssistantProvider:
    return build_research_assistant_provider()


def _project_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": 40401, "message": "Project was not found"},
    )


@router.post("/{project_id}/course-blueprint/generate")
async def generate_blueprint(
    project_id: int, current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAssistantProvider = Depends(get_research_assistant_provider),
):
    try:
        result = await CourseBlueprintService(db).generate(
            current_user_id=current_user.id, project_id=project_id, provider=provider
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except (CourseBlueprintWorkflowError, CourseBlueprintDurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "WORKFLOW_ERROR", "message": str(exc)},
        ) from None
    return success_response(result)


@router.patch("/{project_id}/activities/{activity_id}")
def revise_activity(
    project_id: int, activity_id: int, payload: CourseActivityUpdateRequest,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    try:
        result = CourseBlueprintService(db).revise(
            current_user_id=current_user.id, project_id=project_id,
            activity_id=activity_id, payload=payload,
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except CourseActivityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40410, "message": "Activity was not found"},
        ) from None
    except CourseBlueprintDurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "WORKFLOW_ERROR", "message": str(exc)},
        ) from None
    return success_response(result)


@router.post("/{project_id}/activities/{activity_id}/regenerate")
async def regenerate_activity(
    project_id: int, activity_id: int, current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAssistantProvider = Depends(get_research_assistant_provider),
):
    try:
        result = await CourseBlueprintService(db).regenerate(
            current_user_id=current_user.id, project_id=project_id,
            activity_id=activity_id, provider=provider,
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except CourseActivityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40410, "message": "Activity was not found"},
        ) from None
    except (CourseBlueprintWorkflowError, CourseBlueprintDurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "WORKFLOW_ERROR", "message": str(exc)},
        ) from None
    return success_response(result)


@router.post("/{project_id}/activities/{activity_id}/transform")
def transform_activity(
    project_id: int, activity_id: int, payload: CourseActivityTransformRequest,
    current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    try:
        result = CourseBlueprintService(db).transform(
            current_user_id=current_user.id, project_id=project_id,
            activity_id=activity_id, payload=payload,
        )
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except CourseActivityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40410, "message": "Activity was not found"},
        ) from None
    except (CourseBlueprintWorkflowError, CourseBlueprintDurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40913, "message": str(exc)},
        ) from None
    return success_response(result)
