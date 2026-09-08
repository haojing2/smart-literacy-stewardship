from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.assistants.base import ResearchAssistantProvider
from app.assistants.factory import build_research_assistant_provider
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.course_design import CourseAssessmentUpdateRequest, CourseDesignState
from app.services.course_design_service import CourseDesignService
from app.services.course_assessment_service import (
    CourseAssessmentAlignmentError,
    CourseAssessmentNotFoundError,
    CourseAssessmentService,
    CourseAssessmentWorkflowError,
)
from app.services.project_service import ProjectNotFoundError


router = APIRouter(prefix="/api/v1/projects", tags=["course-design-assessments"])


def get_research_assistant_provider() -> ResearchAssistantProvider:
    return build_research_assistant_provider()


def _project_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40401, "message": "Project was not found"})


@router.post("/{project_id}/assessments/generate")
async def generate_assessments(project_id: int, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db), provider: ResearchAssistantProvider = Depends(get_research_assistant_provider)):
    try:
        result = await CourseAssessmentService(db).generate(current_user_id=current_user.id, project_id=project_id, provider=provider)
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except CourseAssessmentWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "WORKFLOW_ERROR", "message": str(exc)}) from None
    state = CourseDesignService(db).get_course_design_state(current_user_id=current_user.id, project_id=project_id)
    return success_response(CourseDesignState.model_validate(state).model_dump(by_alias=True, mode="json"))


@router.patch("/{project_id}/assessments/{assessment_id}")
def revise_assessment(project_id: int, assessment_id: int, payload: CourseAssessmentUpdateRequest, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = CourseAssessmentService(db).revise(current_user_id=current_user.id, project_id=project_id, assessment_id=assessment_id, payload=payload)
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except CourseAssessmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40409, "message": "Assessment was not found"}) from None
    return success_response(result)


@router.post("/{project_id}/assessments/{assessment_id}/regenerate")
async def regenerate_assessment(project_id: int, assessment_id: int, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db), provider: ResearchAssistantProvider = Depends(get_research_assistant_provider)):
    try:
        result = await CourseAssessmentService(db).regenerate(current_user_id=current_user.id, project_id=project_id, assessment_id=assessment_id, provider=provider)
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except CourseAssessmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": 40409, "message": "Assessment was not found"}) from None
    except CourseAssessmentWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "WORKFLOW_ERROR", "message": str(exc)}) from None
    return success_response(result)


@router.post("/{project_id}/assessments/confirm")
def confirm_assessments(project_id: int, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        result = CourseAssessmentService(db).confirm(current_user_id=current_user.id, project_id=project_id)
    except ProjectNotFoundError:
        raise _project_not_found() from None
    except CourseAssessmentAlignmentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": 40912, "message": str(exc)}) from None
    state = CourseDesignService(db).get_course_design_state(current_user_id=current_user.id, project_id=project_id)
    return success_response(CourseDesignState.model_validate(state).model_dump(by_alias=True, mode="json"))
