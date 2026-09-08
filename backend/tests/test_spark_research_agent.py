from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.agents.research.errors import ResearchAgentConfigurationError, ResearchAgentResponseError
from app.agents.research.spark_agent_client import SparkResearchAgentClient
from app.agents.research.spark_research_agent import SparkResearchAgent
from app.assistants.prompts.research import build_research_chat_messages
from app.schemas.research_assistant import (
    ResearchAnalysisRequest,
    ResearchChatMessageInput,
    ResearchChatRequest,
    ProjectKnowledgeSourceInput,
    ResearchConversationMessage,
    ResearchConversationSummaryRequest,
)


def _analysis_payload(source_excerpt: str = "研究对象：五年级学生") -> str:
    return (
        "```json\n"
        "{"
        '"researchSubjects":["五年级学生"],'
        '"researchTopics":["AI 信息核验"],'
        '"aiLiteracyDimensions":[],"teachingStrategies":[],'
        '"interventionDuration":null,"assessmentTools":[],'
        '"mainFindings":[],"limitations":[],'
        '"teachingImplications":null,'
        f'"sourceExcerpt":"{source_excerpt}",'
        '"evidenceReady":true'
        "}\n```"
    )


class FakeAgentClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.requests: list[list[dict[str, str]]] = []

    async def generate(self, messages: list[dict[str, str]]) -> str:
        self.requests.append(messages)
        return self.responses.pop(0)


def test_research_chat_prompt_separates_summary_recent_messages_and_question() -> None:
    prompt = build_research_chat_messages(
        ResearchChatRequest(
            resource_id=None,
            message="How should I use this evidence?",
            conversation_summary="Teacher is designing a grade five unit.",
            conversation_messages=[
                ResearchConversationMessage(role="user", content="What is cooperative learning?"),
                ResearchConversationMessage(role="assistant", content="It structures peer learning."),
                ResearchConversationMessage(role="user", content="How should I use this evidence?"),
            ],
            project_knowledge_sources=[
                ProjectKnowledgeSourceInput(
                    content="Collaborative planning improved reflection.",
                    filename="study.pdf",
                    file_id=3,
                    chunk_id="chunk-abc",
                    chunk_index=2,
                    score=0.42,
                )
            ],
        )
    )

    assert prompt[0]["role"] == "system"
    assert "knowledge base configured on the Research Agent platform" in prompt[0]["content"]
    assert prompt[1] == {
        "role": "system",
        "content": "[CONVERSATION SUMMARY]\nTeacher is designing a grade five unit.",
    }
    assert prompt[2] == {"role": "user", "content": "What is cooperative learning?"}
    assert prompt[3] == {"role": "assistant", "content": "It structures peer learning."}
    assert prompt[-1]["content"].count("How should I use this evidence?") == 1
    assert "[PROJECT EVIDENCE]" not in prompt[-1]["content"]


def test_research_agent_accepts_plain_natural_language_chat_response() -> None:
    client = FakeAgentClient(["这是讯飞研教智联 Agent 的普通自然语言回答。"])
    response = asyncio.run(
        SparkResearchAgent(client=client).chat(
            ResearchChatRequest(resource_id=None, message="你好")
        )
    )

    assert response.data.message == "这是讯飞研教智联 Agent 的普通自然语言回答。"
    assert response.data.analysis_patch is None
    assert response.data.evidence_interpretations == []
    assert len(client.requests) == 1


def test_client_extracts_sdk_generation_text_without_stringifying_result() -> None:
    result = SimpleNamespace(
        generations=[[SimpleNamespace(message=SimpleNamespace(content=" assistant answer "))]]
    )
    assert SparkResearchAgentClient._extract_generation_text(result) == "assistant answer"

    with pytest.raises(ResearchAgentResponseError):
        SparkResearchAgentClient._extract_generation_text(SimpleNamespace(generations=[]))


def test_client_runs_sync_sdk_call_in_a_worker_thread() -> None:
    client = SparkResearchAgentClient(
        app_id="app",
        api_key="key",
        api_secret="secret",
        agent_url="wss://example.test/assistant",
        timeout_seconds=1,
    )
    client._generate_sync = lambda _messages: "worker result"  # type: ignore[method-assign]

    assert asyncio.run(client.generate([{"role": "user", "content": "hello"}])) == "worker result"


def test_client_rejects_missing_assistant_configuration() -> None:
    client = SparkResearchAgentClient(
        app_id="",
        api_key="",
        api_secret="",
        agent_url="",
    )
    with pytest.raises(ResearchAgentConfigurationError):
        asyncio.run(client.generate([{"role": "user", "content": "hello"}]))


def test_research_agent_merges_system_instructions_into_user_message() -> None:
    messages = SparkResearchAgent._assistant_messages(
        [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "Analyze this."},
        ]
    )
    assert messages == [
        {
            "role": "user",
            "content": "[APPLICATION TASK]\nReturn JSON only.\n\nAnalyze this.",
        }
    ]


def test_research_agent_parses_analysis_and_never_uses_system_role() -> None:
    source = "标题\n研究对象：五年级学生\n正文"
    client = FakeAgentClient([_analysis_payload()])
    response = asyncio.run(
        SparkResearchAgent(client=client).analyze_research(
            ResearchAnalysisRequest(resource_id=1, extracted_text=source)
        )
    )

    assert response.provider == "spark_assistant"
    assert response.data.research_subjects == ["五年级学生"]
    assert response.data.evidence_ready is False
    assert all(item["role"] != "system" for item in client.requests[0])


def test_research_agent_repairs_invalid_json_once() -> None:
    source = "标题\n研究对象：五年级学生\n正文"
    client = FakeAgentClient(["not json", _analysis_payload()])
    response = asyncio.run(
        SparkResearchAgent(client=client).analyze_research(
            ResearchAnalysisRequest(resource_id=1, extracted_text=source)
        )
    )
    assert response.data.source_excerpt == "研究对象：五年级学生"
    assert len(client.requests) == 2


def test_research_agent_discards_unverifiable_source_excerpt_without_failing_analysis() -> None:
    client = FakeAgentClient([_analysis_payload("不存在的原文")])
    response = asyncio.run(
        SparkResearchAgent(client=client).analyze_research(
            ResearchAnalysisRequest(resource_id=1, extracted_text="论文正文")
        )
    )
    assert response.data.source_excerpt is None


def test_research_agent_allows_null_source_excerpt() -> None:
    client = FakeAgentClient([_analysis_payload().replace('"sourceExcerpt":"研究对象：五年级学生"', '"sourceExcerpt":null')])
    response = asyncio.run(
        SparkResearchAgent(client=client).analyze_research(
            ResearchAnalysisRequest(resource_id=1, extracted_text="论文正文")
        )
    )
    assert response.data.source_excerpt is None


def test_research_agent_keeps_stream_endpoint_contract_without_sdk_streaming() -> None:
    client = FakeAgentClient(["完整回答"])

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in SparkResearchAgent(client=client).stream_chat(
                ResearchChatRequest(resource_id=1, message="你好")
            )
        ]

    assert asyncio.run(collect()) == ["完整回答"]


def test_project_knowledge_chat_can_return_an_analysis_patch() -> None:
    client = FakeAgentClient(
        ['{"message":"可为当前教学项目提供研究支持","analysisPatch":{"mainFindings":["ignored"]}}']
    )
    response = asyncio.run(
        SparkResearchAgent(client=client).chat(
            ResearchChatRequest(
                resource_id=None,
                message="有哪些研究支持合作学习？",
                project_title="五年级 AI 素养",
                project_topic="合作学习",
            )
        )
    )

    assert response.data.message == "可为当前教学项目提供研究支持"
    assert response.data.analysis_patch is not None
    assert response.data.analysis_patch.main_findings == ["ignored"]
    assert "knowledge base configured on the Research Agent platform" in client.requests[0][0]["content"]


def test_research_agent_uses_a_dedicated_conversation_summary_prompt() -> None:
    client = FakeAgentClient(['{"summary":"Teacher wants evidence for cooperative learning."}'])
    response = asyncio.run(
        SparkResearchAgent(client=client).summarize_conversation(
            ResearchConversationSummaryRequest(
                existing_summary="The discussion concerns AI literacy.",
                messages=[
                    ResearchChatMessageInput(
                        role="USER", content="What about grade five?"
                    )
                ],
            )
        )
    )

    assert response.data.summary == "Teacher wants evidence for cooperative learning."
    assert "Omit greetings and repetition" in client.requests[0][0]["content"]
