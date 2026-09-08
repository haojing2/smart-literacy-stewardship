from __future__ import annotations

import asyncio
import inspect

import pytest
from pydantic import ValidationError

from app.assistants.base import ResearchAssistantProvider
from app.assistants.factory import build_research_assistant_provider
from app.assistants.mock_research_assistant import MockResearchAssistant
from app.schemas.research_assistant import (
    EvidenceCardGenerationRequest,
    ResearchAnalysisRequest,
    ResearchChatMessageInput,
    ResearchChatRequest,
)
from app.services.research_assistant_service import ResearchAssistantService


def analysis_request() -> ResearchAnalysisRequest:
    return ResearchAnalysisRequest(
        resource_id=101,
        extracted_text="研究主题：学生的 AI 信息核验能力。\n研究对象：五年级学生。",
        project_title="AI 信息核验课程",
        project_topic="AI 信息核验",
    )


def test_mock_analysis_is_deterministic_and_pydantic_validated() -> None:
    provider = MockResearchAssistant()
    request = analysis_request()
    first = asyncio.run(provider.analyze_research(request))
    second = asyncio.run(provider.analyze_research(request))

    assert first == second
    assert first.provider == "mock"
    assert len(first.request_fingerprint) == 64
    assert first.data.research_topics == ["AI 信息核验"]
    assert first.data.evidence_ready is False
    assert first.model_dump(by_alias=True)["requestFingerprint"] == (
        second.request_fingerprint
    )


def test_mock_chat_is_deterministic_for_same_message_and_history() -> None:
    provider = MockResearchAssistant()
    request = ResearchChatRequest(
        resource_id=101,
        message="这项研究的主要局限是什么？",
        history=[
            ResearchChatMessageInput(role="USER", content="请分析这篇研究。"),
            ResearchChatMessageInput(role="ASSISTANT", content="已收到。"),
        ],
    )
    first = asyncio.run(provider.chat(request))
    second = asyncio.run(provider.chat(request))
    assert first == second
    assert first.data.message == (
        "当前研究对象尚未确认。你可以在右侧研究解析区补充研究对象。"
    )
    assert first.data.analysis_patch is None


def test_mock_chat_only_patches_explicit_teacher_facts() -> None:
    provider = MockResearchAssistant()
    initial = asyncio.run(provider.analyze_research(analysis_request())).data
    request = ResearchChatRequest(
        resource_id=101,
        message="研究对象：五年级学生\n主要研究结果：核验表现有所提升",
        analysis=initial,
    )
    response = asyncio.run(provider.chat(request))
    assert response.data.analysis_patch is not None
    assert response.data.analysis_patch.research_subjects == ["五年级学生"]
    assert response.data.analysis_patch.main_findings == ["核验表现有所提升"]
    assert response.data.message == (
        "当前尚未明确教学策略，请补充研究中的教学策略。"
    )


def test_mock_evidence_card_is_always_a_stable_draft() -> None:
    provider = MockResearchAssistant()
    analysis = asyncio.run(provider.analyze_research(analysis_request())).data
    request = EvidenceCardGenerationRequest(
        resource_id=101,
        source_file_name="study.pdf",
        analysis=analysis,
    )
    first = asyncio.run(provider.generate_evidence_card(request))
    second = asyncio.run(provider.generate_evidence_card(request))
    assert first == second
    assert first.data.review_status == "DRAFT"
    assert first.data.source_document == "study.pdf"
    assert first.data.teaching_implication is None


def test_request_schemas_reject_unstructured_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchAnalysisRequest.model_validate(
            {
                "resourceId": 101,
                "extractedText": "正文",
                "unknownAgentOption": True,
            }
        )


def test_business_service_depends_only_on_provider_abstraction() -> None:
    source = inspect.getsource(ResearchAssistantService)
    module_source = inspect.getsource(
        __import__(
            "app.services.research_assistant_service",
            fromlist=["ResearchAssistantService"],
        )
    )
    assert "MockResearchAssistant" not in source
    assert "mock_research_assistant" not in module_source

    provider = build_research_assistant_provider()
    assert isinstance(provider, ResearchAssistantProvider)
    service = ResearchAssistantService(provider)
    result = asyncio.run(service.analyze_research(analysis_request()))
    assert result.provider == "mock"
