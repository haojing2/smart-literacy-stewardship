from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.agents.research.spark_research_agent import SparkResearchAgent
from app.assistants.prompts.research import build_research_chat_messages
from app.services.project_knowledge_service import ProjectKnowledgeSource
from app.services.research_query_rewrite_service import ResearchQueryRewriteService
from app.services.research_chat_service import ResearchChatService, ResearchRetrievalScopeError


QUESTION_1 = "什么是智能化学习支架？"
ANSWER_1 = "智能化学习支架是论文讨论的一种学习支持。"
QUESTION_2 = "智能化学习支架的设计准则包含哪些？"
FOLLOW_UP = "它有哪些设计准则？"
REWRITTEN = "该论文提出的智能化学习支架有哪些设计准则和设计原则？"


class Repository:
    def __init__(self, messages=None) -> None:
        self.messages = messages or []

    def get_owned_project(self, **_kwargs):
        return SimpleNamespace(
            id=42, title="智能化学习支架研究", topic="学习支架", grade=7,
            class_hours=2, student_level=None, student_experience=None,
            class_size=None, lesson_minutes=40, ai_access_mode=None,
            devices_json=None, constraints_json=None, additional_requirements=None,
            context_diagnosis_json=None,
        )

    def get_resource(self, **_kwargs):
        return SimpleNamespace(id=8, original_filename="learning-scaffold.pdf")

    def list_messages(self, **_kwargs):
        return self.messages


class Knowledge:
    def __init__(self, *, sources=None, error: Exception | None = None) -> None:
        self.sources = sources if sources is not None else [
            ProjectKnowledgeSource(
                content="论文提出适应性、渐隐性和学习者控制三项设计准则。",
                project_id=42, filename="learning-scaffold.pdf", file_id=8,
                chunk_id="chunk-design-rules", chunk_index=6, score=0.93,
            )
        ]
        self.error = error
        self.calls = []

    async def search_resource(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.sources

    async def search(self, **_kwargs):
        raise AssertionError("RESOURCE session must not use project search")


class Rewriter:
    def __init__(self, result=REWRITTEN, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = []

    async def rewrite(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


def message(role: str, content: str):
    return SimpleNamespace(role=role, content=content)


def session(summary: str | None = None):
    return SimpleNamespace(id=17, project_id=42, resource_id=8, conversation_summary=summary)


def build_service(repository, knowledge, rewriter) -> ResearchChatService:
    service = ResearchChatService(
        None, SimpleNamespace(), project_knowledge=knowledge, query_rewriter=rewriter
    )  # type: ignore[arg-type]
    service.repository = repository  # type: ignore[assignment]
    return service


def request_for(service: ResearchChatService, question: str):
    return asyncio.run(service._chat_request(
        current_user_id=3, session=session(), content=question, analysis=None,
    ))


def test_query_rewrite_prompt_uses_memory_and_resource_name_without_answering() -> None:
    class Client:
        def __init__(self) -> None:
            self.messages = None

        async def chat(self, messages, **_kwargs):
            self.messages = messages
            return REWRITTEN

    client = Client()
    rewritten = asyncio.run(ResearchQueryRewriteService(client).rewrite(
        conversation_summary="用户正在讨论智能化学习支架。",
        recent_messages=[
            SimpleNamespace(role="USER", content=QUESTION_1),
            SimpleNamespace(role="ASSISTANT", content=ANSWER_1),
        ],
        current_question=FOLLOW_UP,
        project_title="智能化学习支架研究",
        project_topic="学习支架",
        resource_filename="learning-scaffold.pdf",
    ))

    assert rewritten == REWRITTEN
    assert client.messages is not None
    prompt = client.messages[-1]["content"]
    assert "用户正在讨论智能化学习支架" in prompt
    assert QUESTION_1 in prompt
    assert FOLLOW_UP in prompt
    assert "learning-scaffold.pdf" in prompt


def test_query_rewrite_uses_larger_completion_budget() -> None:
    class Client:
        def __init__(self) -> None:
            self.kwargs = None

        async def chat(self, _messages, **kwargs):
            self.kwargs = kwargs
            return "standalone query"

    client = Client()
    asyncio.run(ResearchQueryRewriteService(client).rewrite(
        conversation_summary=None,
        recent_messages=[],
        current_question="它有哪些局限？",
        project_title=None,
        project_topic=None,
    ))

    assert client.kwargs["max_tokens"] == 512
    assert "Do not answer the question" in prompt


def test_first_pdf_turn_retrieves_and_binds_evidence_to_current_question() -> None:
    knowledge = Knowledge()
    rewriter = Rewriter()
    service = build_service(Repository([message("USER", QUESTION_1)]), knowledge, rewriter)
    request = request_for(service, QUESTION_1)
    final = SparkResearchAgent._assistant_messages(build_research_chat_messages(request))

    assert knowledge.calls[0]["query"] == QUESTION_1
    assert rewriter.calls == []
    assert "[RETRIEVED PROJECT EVIDENCE]" in final[-1]["content"]
    assert "chunk-design-rules" in final[-1]["content"]
    assert f"[CURRENT USER QUESTION]\n{QUESTION_1}" in final[-1]["content"]


def test_second_turn_keeps_history_then_binds_evidence_to_current_question() -> None:
    history = [
        message("USER", QUESTION_1), message("ASSISTANT", ANSWER_1),
        message("USER", QUESTION_2),
    ]
    service = build_service(Repository(history), Knowledge(), Rewriter(result=QUESTION_2))
    request = request_for(service, QUESTION_2)
    final = SparkResearchAgent._assistant_messages(build_research_chat_messages(request))

    assert [item["role"] for item in final] == ["user", "assistant", "user"]
    assert final[0]["content"] == QUESTION_1
    assert final[1]["content"] == ANSWER_1
    assert "[RETRIEVED PROJECT EVIDENCE]" not in final[0]["content"]
    assert "[RETRIEVED PROJECT EVIDENCE]" in final[2]["content"]
    assert f"[CURRENT USER QUESTION]\n{QUESTION_2}" in final[2]["content"]


def test_pronoun_followup_uses_rewritten_query_for_resource_retrieval() -> None:
    history = [
        message("USER", "这篇论文提出了什么学习支架？"),
        message("ASSISTANT", ANSWER_1), message("USER", FOLLOW_UP),
    ]
    knowledge = Knowledge()
    rewriter = Rewriter()
    service = build_service(Repository(history), knowledge, rewriter)
    request = request_for(service, FOLLOW_UP)

    assert knowledge.calls[0]["file_id"] == 8
    assert knowledge.calls[0]["query"] == REWRITTEN
    assert request.message == FOLLOW_UP
    assert request.retrieval_query == REWRITTEN
    assert request.query_rewrite_status == "READY"


def test_query_rewrite_failure_falls_back_without_breaking_chat() -> None:
    history = [message("USER", QUESTION_1), message("ASSISTANT", ANSWER_1), message("USER", FOLLOW_UP)]
    knowledge = Knowledge()
    service = build_service(
        Repository(history), knowledge, Rewriter(error=RuntimeError("rewrite unavailable"))
    )
    request = request_for(service, FOLLOW_UP)
    metadata = service._assistant_message_metadata(session(), request)

    assert knowledge.calls[0]["query"] == FOLLOW_UP
    assert request.retrieval_status == "READY"
    assert metadata["retrievalQuery"] == FOLLOW_UP
    assert metadata["queryRewriteStatus"] == "FALLBACK"


def test_empty_retrieval_says_uploaded_resource_exists() -> None:
    service = build_service(Repository([message("USER", QUESTION_1)]), Knowledge(sources=[]), Rewriter())
    request = request_for(service, QUESTION_1)
    prompt = SparkResearchAgent._assistant_messages(build_research_chat_messages(request))[-1]["content"]

    assert request.retrieval_status == "EMPTY"
    assert "Uploaded research resource exists: YES" in prompt
    assert "no sufficiently relevant evidence" in prompt
    assert "Never ask the user to upload or re-upload" in prompt


def test_failed_retrieval_is_degraded_and_preserves_uploaded_resource_status() -> None:
    service = build_service(
        Repository([message("USER", QUESTION_1)]),
        Knowledge(error=RuntimeError("index unavailable")), Rewriter(),
    )
    request = request_for(service, QUESTION_1)
    prompt = SparkResearchAgent._assistant_messages(build_research_chat_messages(request))[-1]["content"]

    assert request.retrieval_status == "FAILED"
    assert request.project_knowledge_sources == []
    assert "Uploaded research resource exists: YES" in prompt
    assert "local retrieval had a technical failure" in prompt
    assert "The uploaded research resource still exists" in prompt


def test_resource_scope_rejects_a_chunk_from_another_pdf() -> None:
    wrong = ProjectKnowledgeSource(
        content="other paper", project_id=42, filename="other.pdf", file_id=9,
        chunk_id="wrong-file", chunk_index=0, score=1.0,
    )
    service = build_service(
        Repository([message("USER", QUESTION_1)]), Knowledge(sources=[wrong]), Rewriter(),
    )
    with pytest.raises(ResearchRetrievalScopeError):
        request_for(service, QUESTION_1)
