"""Shared fixtures and safe runners for the Spark provider demos.

Every fixture uses synthetic IDs and data. These demos call the provider layer
only: they neither create a database session nor write application records.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Awaitable, TypeVar

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pydantic import BaseModel

from app.assistants.spark_client import SparkLLMError
from app.assistants.spark_research_assistant import SparkResearchAssistant
from app.core.config import settings
from app.schemas.course_design import (
    CourseActivityProposal,
    CourseAssessmentGenerationRequest,
    CourseBlueprintGenerationRequest,
    CourseContextDiagnosis,
    CourseContextDiagnosisRequest,
    CourseObjectiveGenerationRequest,
    CoursePedagogyRecommendationRequest,
    CourseQualityCheckRequest,
)
from app.schemas.research_assistant import (
    EvidenceCardGenerationRequest,
    ResearchAnalysisRequest,
    ResearchAnalysisResult,
    ResearchChatRequest,
)
from app.schemas.resource_creation import (
    ResourceBlockTransformProviderRequest,
    ResourceCourseContext,
    ResourceDraftBlock,
    ResourceDraftContent,
    ResourceRevisionProposalRequest,
    ResourceSettingsRecommendationRequest,
    ResourceType,
    TeachingResourceGenerationRequest,
    TeachingResourceReviewRequest,
)

T = TypeVar("T", bound=BaseModel)


def provider() -> SparkResearchAssistant:
    if not settings.spark_api_key:
        raise RuntimeError("SPARK_API_KEY is required in backend/.env")
    return SparkResearchAssistant()


def show(value: BaseModel) -> None:
    print(value.model_dump_json(by_alias=True, indent=2))


def run(coro: Awaitable[T]) -> None:
    try:
        show(asyncio.run(coro))
    except (SparkLLMError, ValueError, RuntimeError) as exc:
        print(f"Demo failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


EXTRACTED_TEXT = (
    "本研究以五年级学生为对象，开展四周的信息核验学习活动。"
    "结果显示，学生能够更多地引用来源证据说明判断。"
)


def analysis() -> ResearchAnalysisResult:
    return ResearchAnalysisResult(
        research_subjects=["五年级学生"],
        research_topics=["AI 信息核验"],
        ai_literacy_dimensions=["信息可信度判断"],
        teaching_strategies=["证据比较"],
        intervention_duration="四周",
        assessment_tools=["学习单"],
        main_findings=["学生能够更多地引用来源证据说明判断"],
        limitations=["样本规模有限"],
        teaching_implications="通过证据比较支持学生形成可解释的信息判断。",
        source_excerpt="结果显示，学生能够更多地引用来源证据说明判断。",
    )


def context_diagnosis() -> CourseContextDiagnosis:
    return CourseContextDiagnosis(
        core_problem="学生需要学习以证据核验 AI 生成信息。",
        existing_foundation="学生能使用搜索工具。",
        learning_difficulties=["辨别来源", "用证据修正判断"],
        constraints=["40 分钟", "小组共用设备"],
    )


def context_request() -> CourseContextDiagnosisRequest:
    return CourseContextDiagnosisRequest(
        project_id=1, grade=5, topic="AI 信息核验", lesson_minutes=40,
        class_size=36, student_experience="学生能使用搜索工具。",
        device_condition="每组一台电脑", prompt="诊断教学情境并提出学习难点。",
    )


def objectives_request() -> CourseObjectiveGenerationRequest:
    return CourseObjectiveGenerationRequest(
        project_id=1, grade=5, topic="AI 信息核验",
        context_diagnosis=context_diagnosis(),
        evidence=[{"title": "研究发现", "content": "证据比较有助于信息判断。"}],
        curriculum_standards=[{"id": 101, "content": "辨析信息来源"}],
        ai_literacy_items=[{"id": 201, "content": "核验 AI 输出"}],
        prompt="生成 2 至 4 项可观察的学习目标。",
    )


def course_context() -> dict[str, object]:
    return {"grade": 5, "lessonMinutes": 40, "classSize": 36, "devices": ["COMPUTER"]}


def objectives() -> list[dict[str, object]]:
    return [
        {"id": 11, "content": "识别 AI 回答中需要核验的信息", "standardRefs": [101], "literacyRefs": [201]},
        {"id": 12, "content": "引用两个来源说明信息判断", "standardRefs": [101], "literacyRefs": [201]},
    ]


def pedagogy_request() -> CoursePedagogyRecommendationRequest:
    return CoursePedagogyRecommendationRequest(
        project_id=1, context=course_context(), objectives=objectives(),
        evidence=[{"title": "研究发现", "content": "证据比较有助于信息判断。"}],
        methods=[
            {"id": 301, "name": "问题探究", "description": "从真实问题开始。"},
            {"id": 302, "name": "合作学习", "description": "小组协作比较证据。"},
        ], prompt="推荐一种教学法并提供备选方案。",
    )


def pedagogy() -> dict[str, object]:
    return {"methodId": 301, "name": "问题探究", "rationale": "支持证据比较", "components": ["真实问题", "小组讨论"]}


def assessments() -> list[dict[str, object]]:
    return [{"id": 21, "objectiveId": 11, "taskContent": "完成来源核验学习单", "criteria": ["引用证据"]}]


def assessment_request() -> CourseAssessmentGenerationRequest:
    return CourseAssessmentGenerationRequest(
        project_id=1, context=course_context(), objectives=objectives(), pedagogy=pedagogy(),
        ai_literacy_items=[{"id": 201, "content": "核验 AI 输出"}],
        evidence=[{"title": "研究发现", "content": "证据比较有助于信息判断。"}],
        prompt="为每个目标设计可观察的评价任务。",
    )


def blueprint_request() -> CourseBlueprintGenerationRequest:
    return CourseBlueprintGenerationRequest(
        project_id=1, context=course_context(), objectives=objectives(), pedagogy=pedagogy(),
        assessments=assessments(), evidence=[{"title": "研究发现", "content": "证据比较有助于信息判断。"}],
        prompt="生成 4 个活动，总时长为 40 分钟。",
    )


def activity() -> CourseActivityProposal:
    return CourseActivityProposal(
        name="来源核验", duration=10, core_task="比较两个来源的证据。",
        teacher_action="示范来源核验步骤。", student_action="小组记录证据。",
        ai_role="EVIDENCE_SUPPORT", assessment="检查学习单。",
        scaffolds=["来源核验表"], objective_refs=[11, 12],
    )


def activities() -> list[dict[str, object]]:
    return [
        {**activity().model_dump(by_alias=True), "id": index}
        for index in range(31, 35)
    ]


def quality_request() -> CourseQualityCheckRequest:
    return CourseQualityCheckRequest(
        project_id=1, context=course_context(), objectives=objectives(), pedagogy=pedagogy(),
        assessments=assessments(), activities=activities(),
        evidence=[{"title": "研究发现", "content": "证据比较有助于信息判断。"}],
        prompt="检查认知负荷、目标对齐和活动衔接。",
    )


def resource_project() -> ResourceCourseContext:
    return ResourceCourseContext(title="AI 信息核验", topic="AI 信息核验", grade="五年级", lesson_minutes=40, devices=["COMPUTER"])


def draft_content() -> ResourceDraftContent:
    return ResourceDraftContent(title="来源核验学习单", blocks=[ResourceDraftBlock(key="task", title="任务", content="比较两个来源并记录证据。")])


def resource_generation_request() -> TeachingResourceGenerationRequest:
    return TeachingResourceGenerationRequest(resource_type=ResourceType.WORKSHEET, project=resource_project(), objectives=objectives(), pedagogy=pedagogy(), assessments=assessments(), activities=activities())


def resource_settings_request() -> ResourceSettingsRecommendationRequest:
    return ResourceSettingsRecommendationRequest(project=resource_project(), selected_types=[ResourceType.WORKSHEET, ResourceType.TASK_CARD], common_settings={"language": "zh-CN"})


def resource_transform_request() -> ResourceBlockTransformProviderRequest:
    return ResourceBlockTransformProviderRequest(resource_type=ResourceType.WORKSHEET, action="ADD_SCAFFOLD", current_content=draft_content(), target_block_key="task", instruction="添加来源核验步骤。")


def resource_review_request() -> TeachingResourceReviewRequest:
    return TeachingResourceReviewRequest(resource_type=ResourceType.WORKSHEET, content=draft_content(), instruction="检查学生是否获得足够支架。")


def resource_revision_request() -> ResourceRevisionProposalRequest:
    return ResourceRevisionProposalRequest(resource_type=ResourceType.WORKSHEET, base_content=draft_content(), user_request="将任务改得更适合基础一般的学生。", target_block_key="task")
