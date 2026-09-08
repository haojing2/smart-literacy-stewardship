from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.course_design import CourseDesignState
from app.services.course_design_service import CourseDesignService, CourseDesignWorkflowStateError
from app.services.project_service import ProjectNotFoundError


router = APIRouter(prefix="/api/v1/projects", tags=["course-design"])


@router.get("/{project_id}/course-design")
def get_course_design_state(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = CourseDesignService(db).get_course_design_state(
            current_user_id=current_user.id, project_id=project_id
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    except CourseDesignWorkflowStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "WORKFLOW_ERROR", "message": str(exc)},
        ) from None

    data = CourseDesignState.model_validate(result).model_dump(by_alias=True, mode="json")
    return success_response(data)
