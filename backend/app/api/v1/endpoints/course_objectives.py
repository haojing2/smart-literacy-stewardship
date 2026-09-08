from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.assistants.base import ResearchAssistantProvider
from app.assistants.factory import build_research_assistant_provider
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.course_design import CourseDesignState, CourseObjectiveCreateRequest, CourseObjectiveUpdateRequest
from app.services.course_design_service import CourseDesignService
from app.services.course_objective_service import (
    CourseObjectiveConfirmationError,
    CourseObjectiveNotFoundError,
    CourseObjectiveService,
    CourseObjectiveWorkflowError,
)
from app.services.project_service import ProjectNotFoundError


router = APIRouter(prefix="/api/v1/projects", tags=["course-design-objectives"])


def get_research_assistant_provider() -> ResearchAssistantProvider:
    return build_research_assistant_provider()


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40401, "message": "Project was not found"})


@router.post("/{project_id}/objectives/generate")
async def generate_objectives(project_id: int, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db), provider: ResearchAssistantProvider = Depends(get_research_assistant_provider)):
    try:
        result = await CourseObjectiveService(db).generate(current_user_id=current_user.id, project_id=project_id, provider=provider)
    except ProjectNotFoundError:
        raise _not_found() from None
    except CourseObjectiveWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "WORKFLOW_ERROR", "message": str(exc)}) from None
    state = CourseDesignService(db).get_course_design_state(current_user_id=current_user.id, project_id=project_id)
    return success_response(CourseDesignState.model_validate(state).model_dump(by_alias=True, mode="json"))


@router.patch("/{project_id}/objectives/{objective_id}")
def revise_objective(project_id: int, objective_id: int, payload: CourseObjectiveUpdateRequest, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = CourseObjectiveService(db).revise(current_user_id=current_user.id, project_id=project_id, objective_id=objective_id, payload=payload)
    except ProjectNotFoundError:
        raise _not_found() from None
    except CourseObjectiveNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40407, "message": "Objective was not found"}) from None
    return success_response(result)


@router.post("/{project_id}/objectives/{objective_id}/keep")
def keep_objective(project_id: int, objective_id: int, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = CourseObjectiveService(db).keep(current_user_id=current_user.id, project_id=project_id, objective_id=objective_id)
    except ProjectNotFoundError:
        raise _not_found() from None
    except CourseObjectiveNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40407, "message": "Objective was not found"}) from None
    return success_response(result)


@router.delete("/{project_id}/objectives/{objective_id}")
def reject_objective(project_id: int, objective_id: int, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        CourseObjectiveService(db).reject(current_user_id=current_user.id, project_id=project_id, objective_id=objective_id)
    except ProjectNotFoundError:
        raise _not_found() from None
    except CourseObjectiveNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40407, "message": "Objective was not found"}) from None
    return success_response({"objectiveId": objective_id, "rejected": True})


@router.post("/{project_id}/objectives")
def add_objective(project_id: int, payload: CourseObjectiveCreateRequest, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = CourseObjectiveService(db).add_teacher_objective(current_user_id=current_user.id, project_id=project_id, payload=payload)
    except ProjectNotFoundError:
        raise _not_found() from None
    return success_response(result)


@router.post("/{project_id}/objectives/confirm")
def confirm_objectives(project_id: int, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = CourseObjectiveService(db).confirm(current_user_id=current_user.id, project_id=project_id)
    except ProjectNotFoundError:
        raise _not_found() from None
    except CourseObjectiveConfirmationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": 40909, "message": str(exc)}) from None
    state = CourseDesignService(db).get_course_design_state(current_user_id=current_user.id, project_id=project_id)
    return success_response(CourseDesignState.model_validate(state).model_dump(by_alias=True, mode="json"))
