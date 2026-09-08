from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.evidence_card import EvidenceCardUpdateRequest
from app.services.evidence_card_draft_service import (
    EvidenceAnalysisStaleError,
    EvidenceCardDraftService,
    EvidenceCardNotFoundError,
)


router = APIRouter(prefix="/api/v1/evidence-cards", tags=["evidence-cards"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": 40406, "message": "Evidence Card was not found"},
    )


@router.get("/{evidence_card_id}")
def get_evidence_card(
    evidence_card_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = EvidenceCardDraftService(db).get_draft(
            current_user_id=current_user.id, evidence_card_id=evidence_card_id
        )
    except EvidenceCardNotFoundError:
        raise _not_found() from None
    return success_response(result.model_dump(by_alias=True, mode="json"))


@router.put("/{evidence_card_id}")
def update_evidence_card(
    evidence_card_id: int,
    payload: EvidenceCardUpdateRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = EvidenceCardDraftService(db).update_draft(
            current_user_id=current_user.id,
            evidence_card_id=evidence_card_id,
            values=payload,
        )
    except EvidenceCardNotFoundError:
        raise _not_found() from None
    except EvidenceAnalysisStaleError as exc:
        raise HTTPException(
            status_code=409, detail={"code": 40905, "message": str(exc)}
        ) from None
    return success_response(result.model_dump(by_alias=True, mode="json"))


@router.post("/{evidence_card_id}/confirm")
def confirm_evidence_card(
    evidence_card_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = EvidenceCardDraftService(db).confirm_draft(
            current_user_id=current_user.id, evidence_card_id=evidence_card_id
        )
    except EvidenceCardNotFoundError:
        raise _not_found() from None
    except EvidenceAnalysisStaleError as exc:
        raise HTTPException(
            status_code=409, detail={"code": 40906, "message": str(exc)}
        ) from None
    return success_response(result.model_dump(by_alias=True, mode="json"))
