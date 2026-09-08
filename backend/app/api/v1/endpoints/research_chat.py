import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.agents.research.base import ResearchAgentProvider
from app.agents.research.errors import ResearchAgentError
from app.agents.research.factory import build_research_agent_provider
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.research_assistant import (
    ResearchAnalysisEditRequest,
    ResearchAnalysisVersionResponse,
    ResearchChatMessageCreateRequest,
    ResearchChatSendMessageResponse,
    ResearchChatSessionCreateRequest,
    ResearchChatSessionResponse,
)
from app.services.research_analysis_service import (
    ResearchAnalysisNotFoundError,
    ResearchAnalysisNotReadyError,
    ResearchAnalysisService,
)
from app.services.research_chat_service import (
    ResearchChatInactiveError,
    ResearchChatNotFoundError,
    ResearchChatService,
    ResearchTextNotReadyError,
)

router = APIRouter(tags=["research-chat"])
logger = logging.getLogger(__name__)


def get_research_agent_provider() -> ResearchAgentProvider:
    return build_research_agent_provider()


def _analysis_response(result: ResearchAnalysisVersionResponse):
    return success_response(result.model_dump(by_alias=True, mode="json"))


@router.post(
    "/api/v1/projects/{project_id}/research-chat/sessions",
    status_code=status.HTTP_201_CREATED,
)
async def create_research_chat_session(
    project_id: int,
    payload: ResearchChatSessionCreateRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAgentProvider = Depends(get_research_agent_provider),
):
    try:
        result = await ResearchChatService(db, provider).create_session(
            current_user_id=current_user.id,
            project_id=project_id,
            request=payload,
        )
    except ResearchChatNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40403, "message": "Research resource was not found"},
        ) from None
    except ResearchTextNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40902, "message": str(exc)},
        ) from None
    except ResearchAgentError as exc:
        logger.warning(
            "Research paper analysis failed project_id=%s exception_type=%s",
            project_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": 50211,
                "message": "论文文本提取成功，但AI结构化研究解析失败",
            },
        ) from exc
    except Exception as exc:
        logger.exception(
            "Research chat session initialization failed project_id=%s mode=%s exception_type=%s",
            project_id,
            "PROJECT_KNOWLEDGE" if payload.resource_id is None else "RESOURCE",
            type(exc).__name__,
        )
        raise
    return success_response(
        ResearchChatSessionResponse.model_validate(result).model_dump(
            by_alias=True,
            mode="json",
        )
    )


@router.get("/api/v1/research-chat/sessions/{session_id}")
def get_research_chat_session(
    session_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAgentProvider = Depends(get_research_agent_provider),
):
    try:
        result = ResearchChatService(db, provider).get_session(
            current_user_id=current_user.id,
            session_id=session_id,
        )
    except ResearchChatNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40404, "message": "Research chat session was not found"},
        ) from None
    return success_response(
        ResearchChatSessionResponse.model_validate(result).model_dump(
            by_alias=True,
            mode="json",
        )
    )


@router.get("/api/v1/projects/{project_id}/research-chat/sessions/latest")
def get_latest_project_research_chat_session(
    project_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAgentProvider = Depends(get_research_agent_provider),
):
    try:
        result = ResearchChatService(db, provider).get_latest_project_session(
            current_user_id=current_user.id, project_id=project_id
        )
    except ResearchChatNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40404, "message": "Research chat session was not found"},
        ) from None
    return success_response(
        ResearchChatSessionResponse.model_validate(result).model_dump(
            by_alias=True, mode="json"
        )
    )


@router.post("/api/v1/research-chat/sessions/{session_id}/messages")
async def send_research_chat_message(
    session_id: int,
    payload: ResearchChatMessageCreateRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAgentProvider = Depends(get_research_agent_provider),
):
    try:
        result = await ResearchChatService(db, provider).send_message(
            current_user_id=current_user.id,
            session_id=session_id,
            content=payload.content,
        )
    except ResearchChatNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40404, "message": "Research chat session was not found"},
        ) from None
    except ResearchChatInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40903, "message": str(exc)},
        ) from None
    except ResearchAgentError as exc:
        logger.warning(
            "Research Agent chat failed session_id=%s exception_type=%s",
            session_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": 50210, "message": str(exc)},
        ) from exc
    return success_response(
        ResearchChatSendMessageResponse.model_validate(result).model_dump(
            by_alias=True,
            mode="json",
        )
    )


@router.post("/api/v1/research-chat/sessions/{session_id}/messages/stream")
async def stream_research_chat_message(
    session_id: int,
    payload: ResearchChatMessageCreateRequest,
    request: Request,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: ResearchAgentProvider = Depends(get_research_agent_provider),
):
    async def events():
        try:
            async for chunk in ResearchChatService(db, provider).stream_message(
                current_user_id=current_user.id,
                session_id=session_id,
                content=payload.content,
            ):
                if await request.is_disconnected():
                    return
                yield f"event: content\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except asyncio.CancelledError:
            raise
        except (ResearchChatNotFoundError, ResearchChatInactiveError) as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
        except ResearchAgentError:
            yield "event: error\ndata: {\"message\": \"AI 服务暂不可用，请稍后重试\"}\n\n"
        except RuntimeError:
            yield "event: error\ndata: {\"message\": \"对话生成失败，请稍后重试\"}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.put("/api/v1/research-chat/sessions/{session_id}/analysis")
def update_research_analysis(
    session_id: int,
    payload: ResearchAnalysisEditRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ResearchAnalysisService(db).update_analysis(
            current_user_id=current_user.id,
            session_id=session_id,
            request=payload,
        )
    except ResearchAnalysisNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40405, "message": "Research analysis was not found"},
        ) from None
    return _analysis_response(result)


@router.post("/api/v1/research-chat/sessions/{session_id}/analysis/confirm")
def confirm_research_analysis(
    session_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ResearchAnalysisService(db).confirm_analysis(
            current_user_id=current_user.id,
            session_id=session_id,
        )
    except ResearchAnalysisNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40405, "message": "Research analysis was not found"},
        ) from None
    except ResearchAnalysisNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40904, "message": str(exc)},
        ) from None
    return _analysis_response(result)
