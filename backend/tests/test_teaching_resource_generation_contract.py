from __future__ import annotations

import asyncio
import copy
import json

import pytest

from app.assistants.prompts.resource_creation import (
    RESOURCE_OUTPUT_TEMPLATES,
    build_teaching_resource_messages,
    normalize_assessment_content,
    validate_assessment_content,
)
from app.assistants.spark_research_assistant import SparkResearchAssistant
from app.assistants.spark_client import SparkOutputLengthError
from app.schemas.resource_creation import ResourceType, TeachingResourceGenerationRequest, TeachingResourceGenerationResult


class SequencedJsonClient:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.requests: list[list[dict[str, str]]] = []

    async def chat_json(self, messages, **kwargs):
        self.requests.append(messages)
        return self.responses.pop(0)


def _request(resource_type: ResourceType = ResourceType.DISCUSSION) -> TeachingResourceGenerationRequest:
    return TeachingResourceGenerationRequest.model_validate({
        "resourceType": resource_type,
        "project": {"title": "人工智能素养", "grade": 7},
        "objectives": [{"id": 1, "content": "比较不同回答"}],
        "pedagogy": {"method": "discussion"},
        "assessments": [{"objectiveId": 1, "method": "observation"}],
        "activities": [{"id": 1, "name": "小组讨论"}],
        "researchEvidence": [{"finding": "不应发送"}],
        "courseBlueprint": {"duplicate": True},
    })


def test_resource_prompt_uses_fixed_template_without_full_json_schema() -> None:
    prompt = json.loads(build_teaching_resource_messages(_request())[1]["content"])

    assert "resultSchema" not in prompt
    assert "researchBasedEvidence" not in prompt["context"]
    assert "courseBlueprint" not in prompt["context"]["confirmedCourseDesign"]
    assert prompt["outputTemplate"] == RESOURCE_OUTPUT_TEMPLATES[ResourceType.DISCUSSION]
    assert [block["key"] for block in prompt["outputTemplate"]["content"]["blocks"]] == [
        "question_1", "question_2", "question_3",
    ]
    rules = " ".join(prompt["outputRules"])
    assert "fill content only" in rules
    assert "do not add fields" in rules


def test_every_resource_type_has_the_required_fixed_block_keys() -> None:
    expected = {
        ResourceType.WORKSHEET: ["learning_goal", "task_1", "task_2", "task_3", "reflection"],
        ResourceType.TASK_CARD: ["task_1", "task_2", "task_3"],
        ResourceType.AI_CASE: ["scenario", "dialogue", "judgement", "discussion"],
        ResourceType.DISCUSSION: ["question_1", "question_2", "question_3"],
        ResourceType.ASSESSMENT: ["criteria", "rubric", "evidence"],
        ResourceType.REFLECTION: ["learning_gain", "evidence_and_difficulty", "next_action"],
        ResourceType.TEACHER_GUIDE: ["overview", "lesson_flow", "assessment_reminder"],
    }
    for resource_type, keys in expected.items():
        blocks = RESOURCE_OUTPUT_TEMPLATES[resource_type]["content"]["blocks"]
        assert [block["key"] for block in blocks] == keys


def test_root_block_payload_is_normalized_without_llm_repair() -> None:
    invalid_payload = {
        "title": "讨论题",
        "key": "question_1",
        "content": "为什么需要核查 AI 回答？",
        "changeSummary": "初次生成",
    }
    client = SequencedJsonClient([invalid_payload])
    assistant = SparkResearchAssistant(client=client)  # type: ignore[arg-type]

    result = asyncio.run(assistant._from_messages(
        build_teaching_resource_messages(_request()),
        TeachingResourceGenerationResult,
        resource_type=ResourceType.DISCUSSION,
    ))

    assert result.content.blocks[0].key == "question_1"
    assert len(client.requests) == 1


def test_resource_length_retry_is_limited_to_8192_then_16384() -> None:
    valid = RESOURCE_OUTPUT_TEMPLATES[ResourceType.DISCUSSION]

    class LengthThenSuccessClient:
        def __init__(self) -> None:
            self.max_tokens: list[int] = []

        async def chat_json(self, messages, **kwargs):
            self.max_tokens.append(kwargs["max_tokens"])
            if len(self.max_tokens) == 1:
                raise SparkOutputLengthError("truncated", reasoning_tokens=8000)
            return valid

    client = LengthThenSuccessClient()
    assistant = SparkResearchAssistant(client=client)  # type: ignore[arg-type]
    asyncio.run(assistant._from_messages(
        build_teaching_resource_messages(_request()),
        TeachingResourceGenerationResult,
        resource_type=ResourceType.DISCUSSION,
    ))

    assert client.max_tokens == [8192, 16384]


def test_assessment_legacy_table_is_normalized_for_stable_rendering() -> None:
    content = {
        "title": "评价工具",
        "metadata": {},
        "blocks": [
            {"key": "criteria", "title": "标准", "content": {
                "items": [{"title": f"标准{i}", "description": "说明"} for i in range(4)],
            }},
            {"key": "rubric", "title": "量规", "content": {
                "headers": ["指标", "表现", "证据"],
                "data": [[f"指标{i}", "达成", "作品"] for i in range(4)],
            }},
            {"key": "evidence", "title": "证据", "content": {
                "items": [{"title": "课堂表现", "description": "观察记录"}],
            }},
        ],
    }

    normalized = normalize_assessment_content(content)
    rubric = normalized["blocks"][1]["content"]
    assert rubric["type"] == "table"
    assert rubric["columns"] == [
        {"key": "指标", "label": "指标"},
        {"key": "表现", "label": "表现"},
        {"key": "证据", "label": "证据"},
    ]
    assert len(rubric["rows"]) == 3
    assert len(normalized["blocks"][0]["content"]["items"]) == 3
    validate_assessment_content(normalized)


def test_assessment_validator_rejects_incomplete_table_rows() -> None:
    invalid = json.loads(json.dumps(RESOURCE_OUTPUT_TEMPLATES[ResourceType.ASSESSMENT]))["content"]
    invalid["blocks"][1]["content"]["rows"][0].pop("evidence")

    with pytest.raises(ValueError, match="every column key"):
        validate_assessment_content(invalid)


def test_assessment_repair_sends_only_invalid_blocks_errors_and_template() -> None:
    invalid = copy.deepcopy(RESOURCE_OUTPUT_TEMPLATES[ResourceType.ASSESSMENT])
    invalid["content"]["blocks"][1]["content"]["rows"][0].pop("evidence")
    repaired = copy.deepcopy(RESOURCE_OUTPUT_TEMPLATES[ResourceType.ASSESSMENT])
    client = SequencedJsonClient([invalid, repaired])
    assistant = SparkResearchAssistant(client=client)  # type: ignore[arg-type]

    asyncio.run(assistant.generate_teaching_resource(_request(ResourceType.ASSESSMENT)))

    assert len(client.requests) == 2
    assert len(client.requests[1]) == 2
    repair = json.loads(client.requests[1][1]["content"])
    assert set(repair) == {"task", "validationError", "invalidBlockJson", "outputTemplate"}
    assert "context" not in repair
    assert repair["task"] == "Fix JSON structure only. Do not regenerate or rewrite the teaching content."
