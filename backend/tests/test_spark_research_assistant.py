from __future__ import annotations

import asyncio

from app.assistants.spark_research_assistant import SparkResearchAssistant
from app.schemas.course_design import CourseContextDiagnosis, CourseContextDiagnosisRequest, CourseObjectiveGenerationRequest
from app.schemas.research_assistant import ResearchAnalysisRequest


class FakeSparkClient:
    async def chat_json(self, _messages, *, repair=True):
        return {
            "researchSubjects": [], "researchTopics": ["AI literacy"],
            "aiLiteracyDimensions": [], "teachingStrategies": [],
            "interventionDuration": None, "assessmentTools": [], "mainFindings": [],
            "limitations": [], "teachingImplications": None,
            "sourceExcerpt": "source sentence", "evidenceReady": True,
        }

    async def stream_chat(self, _messages):
        yield "streamed"


def test_spark_analysis_validates_mock_client_output_and_overrides_readiness() -> None:
    provider = SparkResearchAssistant(client=FakeSparkClient())
    response = asyncio.run(provider.analyze_research(ResearchAnalysisRequest(
        resource_id=1, extracted_text="source sentence"
    )))
    assert response.provider == "spark"
    assert response.data.evidence_ready is False
    assert response.data.source_excerpt == "source sentence"


def test_spark_stream_chat_delegates_to_client() -> None:
    from app.schemas.research_assistant import ResearchChatRequest

    async def collect() -> list[str]:
        return [
            value
            async for value in SparkResearchAssistant(client=FakeSparkClient()).stream_chat(
                ResearchChatRequest(resource_id=1, message="hello")
            )
        ]

    assert asyncio.run(collect()) == ["streamed"]


def test_spark_context_diagnosis_accepts_valid_structured_json() -> None:
    class DiagnosisClient:
        async def chat_json(self, _messages, *, repair=True):
            return {
                "coreProblem": "缺少信息核验意识", "existingFoundation": "学生会使用 AI 问答",
                "learningDifficulties": ["比较来源可信度"], "constraints": ["每组共用一台平板"],
            }

    diagnosis = asyncio.run(SparkResearchAssistant(client=DiagnosisClient()).diagnose_course_context(
        CourseContextDiagnosisRequest(projectId=1, grade=4, topic="信息核验", lessonMinutes=40, classSize=42, studentExperience="会简单问答", deviceCondition="平板", prompt="诊断")
    ))
    assert diagnosis.core_problem == "缺少信息核验意识"


def test_spark_repairs_unknown_database_id_once_before_contract_error() -> None:
    class RepairingClient:
        def __init__(self) -> None:
            self.calls = 0

        async def chat_json(self, _messages, *, repair=True):
            self.calls += 1
            return {
                "objectives": [
                    {"content": "识别待核验信息", "rationale": "可观察", "standardRefs": [999], "literacyRefs": []},
                    {"content": "使用证据修订回答", "rationale": "可评价", "standardRefs": [1], "literacyRefs": []},
                ]
            }

    client = RepairingClient()
    result = asyncio.run(SparkResearchAssistant(client=client).generate_course_objectives(
        CourseObjectiveGenerationRequest(
            projectId=1, grade=4, topic="信息核验", prompt="生成目标",
            contextDiagnosis=CourseContextDiagnosis(coreProblem="缺少核验", existingFoundation="会提问", learningDifficulties=["比较来源"], constraints=["设备有限"]),
            curriculumStandards=[{"id": 1, "content": "标准", "performance": "表现"}],
        )
    ))
    assert [item.standard_refs for item in result.objectives] == [[1], [1]]
    assert client.calls == 2
