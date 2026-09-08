from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.services.design_evidence_service import (
    DesignEvidenceBusinessNotFoundError,
    DesignEvidenceService,
)
from app.services.project_service import ProjectNotFoundError


router = APIRouter(prefix="/api/v1/projects", tags=["course-design-evidence"])


@router.get("/{project_id}/design-evidence")
def get_design_evidence(
    project_id: int,
    biz_type: str = Query(..., alias="bizType", min_length=1),
    biz_id: int = Query(..., alias="bizId", gt=0),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = DesignEvidenceService(db).get_design_evidence(
            current_user_id=current_user.id,
            project_id=project_id,
            biz_type=biz_type,
            biz_id=biz_id,
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    except DesignEvidenceBusinessNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40411, "message": "Design item was not found"},
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": 42211, "message": str(exc)},
        ) from None
    return success_response(result)
