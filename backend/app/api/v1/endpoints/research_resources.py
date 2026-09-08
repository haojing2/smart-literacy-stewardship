from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.research import (
    ResearchResourceUploadResponse,
    ResearchTextExtractionResponse,
)
from app.services.document_parser_service import DocumentParsingError
from app.services.project_service import ProjectNotFoundError
from app.services.research_resource_service import (
    InvalidResearchFileError,
    ResearchFileTooLargeError,
    ResearchResourceService,
)
from app.services.research_text_extraction_service import (
    ResearchResourceNotFoundError,
    ResearchTextExtractionService,
    TextExtractionInProgressError,
)

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/research-resources",
    tags=["research-resources"],
)
resource_router = APIRouter(
    prefix="/api/v1/research-resources",
    tags=["research-resources"],
)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_research_resource(
    project_id: int,
    file: UploadFile = File(...),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = await ResearchResourceService(db).upload(
            current_user_id=current_user.id,
            project_id=project_id,
            upload=file,
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40401, "message": "Project was not found"},
        ) from None
    except InvalidResearchFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"code": 41501, "message": str(exc)},
        ) from None
    except ResearchFileTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail={"code": 41301, "message": str(exc)},
        ) from None

    data = ResearchResourceUploadResponse.model_validate(result.response).model_dump(
        by_alias=True,
        mode="json",
    )
    return success_response(data)


@resource_router.post("/{resource_id}/extract-text")
def extract_research_resource_text(
    resource_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ResearchTextExtractionService(db).extract_text(
            current_user_id=current_user.id,
            resource_id=resource_id,
        )
    except ResearchResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40402, "message": "Research resource was not found"},
        ) from None
    except TextExtractionInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40901, "message": str(exc)},
        ) from None
    except DocumentParsingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": 42202, "message": str(exc)},
        ) from None

    data = ResearchTextExtractionResponse.model_validate(result).model_dump(
        by_alias=True,
        mode="json",
    )
    return success_response(data)
