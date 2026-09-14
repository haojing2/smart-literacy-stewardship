from __future__ import annotations

import asyncio
import copy
import json

import pytest

from app.assistants.prompts.resource_creation import RESOURCE_OUTPUT_TEMPLATES
from app.assistants.spark_client import SparkResponseParseError, SparkTimeoutError
from app.assistants.spark_research_assistant import SparkResearchAssistant
from app.core.config import settings
from app.schemas.resource_creation import ResourceType, TeachingResourceGenerationRequest


def _request() -> TeachingResourceGenerationRequest:
    return TeachingResourceGenerationRequest.model_validate({
        "resourceType": "ASSESSMENT",
        "project": {
            "title": "AI 信息核查",
            "topic": "判断生成式 AI 回答的可靠性",
            "grade": 8,
            "lessonMinutes": 45,
            "classSize": 36,
            "studentLevel": "能够进行基础检索",
            "constraints": ["每组仅一台设备"],
        },
        "objectives": [{
            "id": 101,
            "content": "使用证据判断 AI 回答的可靠性",
            "standardRefs": ["redundant-standard"],
            "rationale": "very long redundant rationale",
        }],
        "activities": [{
            "id": 201,
            "sequenceNo": 2,
            "name": "证据核查",
            "duration": 25,
            "objectiveRefs": [101],
            "coreTask": "对照来源核查回答",
            "teacherAction": "提示证据标准",
            "studentAction": "标注可疑陈述",
            "scaffolds": ["核查清单"],
        }],
        "assessments": [{
            "id": 301,
            "objectiveId": 101,
            "task": "提交核查记录",
            "criteria": ["证据相关", "结论合理"],
            "rationale": "redundant assessment rationale",
        }],
        "commonSettings": {"language": "zh-CN"},
        "resourceSettings": {"levels": 3},
    })


def _context(activity_id: int = 201) -> dict[str, object]:
    return {
        "courseSummary": "核查 AI 回答的可靠性。",
        "learnerProfile": "八年级，具备基础检索能力。",
        "implementationConstraints": ["每组仅一台设备"],
        "activitySummaries": [{
            "activityId": activity_id,
            "sequenceNo": 2,
            "summary": "学生对照来源标注可疑陈述。",
        }],
        "assessmentSummaries": [{
            "assessmentId": 301,
            "objectiveId": 101,
            "summary": "依据核查记录评价证据与结论。",
        }],
        "generationFocus": ["可观察的证据使用"],
    }


class RecordingClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[list[dict[str, str]], dict[str, object]]] = []

    async def chat_json(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _valid_resource() -> dict[str, object]:
    return copy.deepcopy(RESOURCE_OUTPUT_TEMPLATES[ResourceType.ASSESSMENT])


def test_context_then_generation_use_independent_models_and_normalized_prompt(monkeypatch) -> None:
    monkeypatch.setattr(settings, "spark_resource_context_enabled", True)
    client = RecordingClient([_context(), _valid_resource()])
    result = asyncio.run(SparkResearchAssistant(client=client).generate_teaching_resource(_request()))  # type: ignore[arg-type]

    assert result.title
    assert [call[1]["model_id"] for call in client.calls] == [
        "spark-x2.5-1.7b", "spark-x2.5-4b",
    ]
    final_prompt = json.loads(client.calls[1][0][1]["content"])
    normalized = final_prompt["context"]["normalizedContext"]
    assert normalized["courseSummary"] == "核查 AI 回答的可靠性。"
    serialized = client.calls[1][0][1]["content"]
    assert "redundant-standard" not in serialized
    assert "very long redundant rationale" not in serialized
    assert "redundant assessment rationale" not in serialized


@pytest.mark.parametrize(
    "context_failure",
    [SparkResponseParseError("invalid JSON"), SparkTimeoutError("timeout")],
)
def test_context_provider_failures_are_fail_open(context_failure: Exception, monkeypatch) -> None:
    monkeypatch.setattr(settings, "spark_resource_context_enabled", True)
    client = RecordingClient([context_failure, _valid_resource()])
    result = asyncio.run(SparkResearchAssistant(client=client).generate_teaching_resource(_request()))  # type: ignore[arg-type]

    assert result.title
    assert len(client.calls) == 2
    final_prompt = json.loads(client.calls[1][0][1]["content"])
    assert final_prompt["context"]["normalizedContext"]["activitySummaries"][0]["activityId"] == 201
    assert client.calls[1][1]["model_id"] == "spark-x2.5-4b"


def test_unknown_context_activity_id_falls_back_and_generation_continues(monkeypatch) -> None:
    monkeypatch.setattr(settings, "spark_resource_context_enabled", True)
    client = RecordingClient([_context(activity_id=999), _valid_resource()])
    asyncio.run(SparkResearchAssistant(client=client).generate_teaching_resource(_request()))  # type: ignore[arg-type]

    final_prompt = json.loads(client.calls[1][0][1]["content"])
    assert final_prompt["context"]["normalizedContext"]["activitySummaries"][0]["activityId"] == 201


def test_authoritative_facts_are_exact_and_settings_are_original(monkeypatch) -> None:
    monkeypatch.setattr(settings, "spark_resource_context_enabled", True)
    client = RecordingClient([_context(), _valid_resource()])
    asyncio.run(SparkResearchAssistant(client=client).generate_teaching_resource(_request()))  # type: ignore[arg-type]

    prompt = json.loads(client.calls[1][0][1]["content"])
    context = prompt["context"]
    assert context["authoritativeFacts"] == {
        "course": {
            "title": "AI 信息核查", "topic": "判断生成式 AI 回答的可靠性",
            "grade": 8, "lessonMinutes": 45, "classSize": 36,
        },
        "objectives": [{"id": 101, "content": "使用证据判断 AI 回答的可靠性"}],
        "activities": [{
            "id": 201, "sequenceNo": 2, "name": "证据核查", "duration": 25,
            "objectiveRefs": [101],
        }],
        "assessments": [{"id": 301, "objectiveId": 101}],
    }
    assert context["resourceSettings"] == {
        "commonSettings": {"language": "zh-CN"},
        "currentTypeSettings": {"levels": 3},
    }


def test_context_prompt_contains_only_resource_specific_course_design(monkeypatch) -> None:
    monkeypatch.setattr(settings, "spark_resource_context_enabled", True)
    request = _request().model_copy(update={"resource_type": ResourceType.WORKSHEET})
    client = RecordingClient([{"activitySummaries": [{
        "activityId": 201, "sequenceNo": 2, "summary": "核查",
    }]}, copy.deepcopy(RESOURCE_OUTPUT_TEMPLATES[ResourceType.WORKSHEET])])
    asyncio.run(SparkResearchAssistant(client=client).generate_teaching_resource(request))  # type: ignore[arg-type]

    context_prompt = json.loads(client.calls[0][0][1]["content"])
    assert set(context_prompt["confirmedCourseDesign"]) == {"objectives", "activities"}
    assert "assessments" not in context_prompt["confirmedCourseDesign"]
