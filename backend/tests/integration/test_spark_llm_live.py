import asyncio
import os

import pytest

from app.assistants.spark_client import SparkLLMClient
from app.assistants.spark_research_assistant import SparkResearchAssistant
from app.schemas.course_design import (
    CourseContextDiagnosis,
    CourseContextDiagnosisRequest,
    CourseObjectiveGenerationRequest,
)
from app.schemas.research_assistant import ResearchChatMessageInput
from app.schemas.resource_creation import (
    ResourceType,
    TeachingResourceGenerationRequest,
)
from app.services.research_query_rewrite_service import ResearchQueryRewriteService


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SPARK_LIVE_TESTS") != "1",
    reason="set RUN_SPARK_LIVE_TESTS=1 to call the real Spark API",
)


def test_spark_llm_live_chat() -> None:
    response = asyncio.run(
        SparkLLMClient().chat([{"role": "user", "content": "你好"}])
    )
    assert response.strip()


def test_research_query_rewrite_live() -> None:
    rewritten = asyncio.run(
        ResearchQueryRewriteService().rewrite(
            conversation_summary="用户正在讨论一篇论文的研究主题。",
            recent_messages=[
                ResearchChatMessageInput(
                    role="USER", content="这篇论文研究了什么？"
                ),
                ResearchChatMessageInput(
                    role="ASSISTANT", content="论文研究了智能化学习支架。"
                ),
            ],
            current_question="它有什么局限？",
            project_title="论文研读",
            project_topic="智能化学习支架",
            resource_filename="paper.pdf",
        )
    )
    assert rewritten.strip()


def test_course_context_diagnosis_live() -> None:
    result = asyncio.run(
        SparkResearchAssistant().diagnose_course_context(
            CourseContextDiagnosisRequest(
                projectId=1,
                grade=7,
                topic="核验 AI 生成的信息",
                lessonMinutes=40,
                classSize=36,
                studentExperience="学生能使用生成式 AI 完成简单问答",
                deviceCondition="每组一台平板电脑",
                prompt="简要诊断本课的学习基础、难点与约束。",
            )
        )
    )
    assert result.core_problem.strip()


def test_course_objective_generation_live() -> None:
    result = asyncio.run(
        SparkResearchAssistant().generate_course_objectives(
            CourseObjectiveGenerationRequest(
                projectId=1,
                grade=7,
                topic="核验 AI 生成的信息",
                contextDiagnosis=CourseContextDiagnosis(
                    coreProblem="学生容易直接相信 AI 回答",
                    existingFoundation="能够进行关键词检索",
                    learningDifficulties=["比较不同来源的可信度"],
                    constraints=["每组一台平板电脑"],
                ),
                curriculumStandards=[
                    {"id": 1, "content": "能依据证据判断信息可信度"}
                ],
                prompt="生成两个可观察、可评价的课程目标。",
            )
        )
    )
    assert len(result.objectives) >= 2
    assert all(set(item.standard_refs).issubset({1}) for item in result.objectives)


def test_teaching_resource_generation_live() -> None:
    request = TeachingResourceGenerationRequest.model_validate(
        {
            "resourceType": ResourceType.WORKSHEET,
            "project": {
                "title": "AI 信息核验",
                "topic": "核验 AI 生成的信息",
                "grade": 7,
                "lessonMinutes": 40,
            },
            "objectives": [
                {"id": 1, "content": "能依据证据判断 AI 回答的可信度"}
            ],
            "pedagogy": {"description": "探究学习"},
            "assessments": [
                {"objectiveId": 1, "task": "说明判断依据"}
            ],
            "activities": [
                {"id": 1, "name": "证据核验", "duration": 40}
            ],
            "courseBlueprint": {"totalActivityMinutes": 40},
            "commonSettings": {"languageStyle": "适合七年级学生"},
            "resourceSettings": {"quantity": 1},
        }
    )
    result = asyncio.run(
        SparkResearchAssistant().generate_teaching_resource(request)
    )
    assert result.title.strip()
    assert result.content.blocks
