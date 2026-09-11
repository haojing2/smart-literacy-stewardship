from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.course_design import router as course_design_router
from app.api.v1.endpoints.course_objectives import router as course_objectives_router
from app.api.v1.endpoints.course_pedagogy import router as course_pedagogy_router
from app.api.v1.endpoints.course_assessments import router as course_assessments_router
from app.api.v1.endpoints.course_blueprint import router as course_blueprint_router
from app.api.v1.endpoints.design_evidence import router as design_evidence_router
from app.api.v1.endpoints.course_quality import router as course_quality_router
from app.api.v1.endpoints.resource_creation import router as resource_creation_router
from app.api.v1.endpoints.admin_users import router as admin_users_router
from app.api.v1.endpoints.admin_system import router as admin_system_router
from app.api.v1.endpoints.research_chat import router as research_chat_router
from app.api.v1.endpoints.evidence_cards import router as evidence_cards_router
from app.api.v1.endpoints.research_resources import (
    resource_router as research_resource_actions_router,
    router as research_resources_router,
)
from app.core.responses import error_response
from app.assistants.spark_client import (
    SparkConfigurationError,
    SparkContractError,
    SparkLLMError,
    SparkNetworkError,
    SparkResponseParseError,
    SparkTimeoutError,
)
from app.agents.research.errors import (
    ResearchAgentConfigurationError,
    ResearchAgentConnectionError,
    ResearchAgentContractError,
    ResearchAgentError,
    ResearchAgentParseError,
    ResearchAgentResponseError,
    ResearchAgentTimeoutError,
)
from app.db.session import engine
from app.core.config import settings


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.debug:
        logger.info(
            "Spark OpenAI-compatible configuration provider=%s base_url=%s model=%s timeout=%s api_key_configured=%s",
            settings.llm_provider,
            settings.spark_api_base,
            settings.spark_model_id,
            settings.spark_timeout_seconds,
            bool(settings.spark_api_key),
        )
    yield


app = FastAPI(
    title="Smart Literacy Stewardship API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            detail.get("code", exc.status_code),
            detail.get("message", str(exc.detail)),
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            **error_response(42201, "Request validation failed"),
            "errors": jsonable_encoder(exc.errors()),
        },
    )


@app.exception_handler(SparkLLMError)
async def spark_exception_handler(_: Request, exc: SparkLLMError) -> JSONResponse:
    if isinstance(exc, SparkTimeoutError):
        status_code, code, message = status.HTTP_504_GATEWAY_TIMEOUT, "AI_TIMEOUT", "AI 服务响应时间较长，请稍后重试"
    elif isinstance(exc, SparkResponseParseError):
        status_code, code, message = status.HTTP_502_BAD_GATEWAY, "AI_INVALID_JSON", "AI 服务返回了无法解析的结构化结果"
    elif isinstance(exc, SparkContractError):
        status_code, code, message = status.HTTP_422_UNPROCESSABLE_ENTITY, "AI_CONTRACT_ERROR", "AI 服务返回的数据不符合课程设计约束"
    elif isinstance(exc, (SparkConfigurationError, SparkNetworkError)):
        status_code, code, message = status.HTTP_503_SERVICE_UNAVAILABLE, "AI_PROVIDER_UNAVAILABLE", "AI 服务暂不可用，请稍后重试"
    else:
        status_code, code, message = status.HTTP_503_SERVICE_UNAVAILABLE, "AI_PROVIDER_UNAVAILABLE", "AI 服务暂不可用，请稍后重试"
    return JSONResponse(status_code=status_code, content=error_response(code, message))


@app.exception_handler(ResearchAgentError)
async def research_agent_exception_handler(_: Request, exc: ResearchAgentError) -> JSONResponse:
    if isinstance(exc, ResearchAgentTimeoutError):
        status_code, code, message = status.HTTP_504_GATEWAY_TIMEOUT, "RESEARCH_AGENT_TIMEOUT", "研教智联服务响应时间较长，请稍后重试"
    elif isinstance(exc, (ResearchAgentParseError, ResearchAgentResponseError)):
        status_code, code, message = status.HTTP_502_BAD_GATEWAY, "RESEARCH_AGENT_INVALID_RESPONSE", "研教智联服务返回了无法处理的结果"
    elif isinstance(exc, ResearchAgentContractError):
        status_code, code, message = status.HTTP_502_BAD_GATEWAY, "RESEARCH_AGENT_CONTRACT_ERROR", "研教智联服务返回的数据不符合约定格式"
    elif isinstance(exc, ResearchAgentConfigurationError):
        status_code, code, message = status.HTTP_503_SERVICE_UNAVAILABLE, "RESEARCH_AGENT_NOT_CONFIGURED", "研教智联服务尚未配置"
    elif isinstance(exc, ResearchAgentConnectionError):
        status_code, code, message = status.HTTP_503_SERVICE_UNAVAILABLE, "RESEARCH_AGENT_UNAVAILABLE", "研教智联服务暂不可用，请稍后重试"
    else:
        status_code, code, message = status.HTTP_503_SERVICE_UNAVAILABLE, "RESEARCH_AGENT_UNAVAILABLE", "研教智联服务暂不可用，请稍后重试"
    return JSONResponse(status_code=status_code, content=error_response(code, message))


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(50000, "Internal server error"),
    )

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(course_design_router)
app.include_router(course_objectives_router)
app.include_router(course_pedagogy_router)
app.include_router(course_assessments_router)
app.include_router(course_blueprint_router)
app.include_router(design_evidence_router)
app.include_router(course_quality_router)
app.include_router(resource_creation_router)
app.include_router(admin_users_router)
app.include_router(admin_system_router)
app.include_router(research_chat_router)
app.include_router(evidence_cards_router)
app.include_router(research_resources_router)
app.include_router(research_resource_actions_router)


@app.get("/")
def root():
    return {
        "name": "Smart Literacy Stewardship",
        "version": "2.0.0",
        "status": "running"
    }


@app.get("/api/v1/health")
def health():
    database_status = "DOWN"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        database_status = "UP"

    except Exception as e:
        print(e)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "api": "UP",
            "database": database_status
        }
    }



print("python -m fastapi dev app/main.py")
