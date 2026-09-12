from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.assistants.spark_client import (
    SparkContractError,
    SparkOutputLengthError,
    SparkTimeoutError,
)
from app.assistants.spark_research_assistant import SparkResearchAssistant
from app.core.config import settings
from app.schemas.research_assistant import (
    ResearchAnalysisPatch,
    ResearchAnalysisRequest,
    ResearchAnalysisResult,
    ResearchAnalysisSupplementRequest,
)
from app.services.document_parser_service import DocumentParsingError
from app.services.evidence_readiness_service import EvidenceReadinessService
from app.services.evidence_card_draft_service import EvidenceCardDraftService
from app.services.project_knowledge_service import ProjectKnowledgeSource
from app.services.research_analysis_evidence_service import (
    RESEARCH_ANALYSIS_FIELD_QUERIES,
    ResearchAnalysisEvidenceCollector,
)
from app.services.research_analysis_extraction_service import (
    ResearchAnalysisExtractionService,
)
from app.services.research_text_extraction_service import ResearchTextExtractionService


class FieldKnowledge:
    async def search_resource(self, *, project_id, file_id, query, top_k):
        field = next(
            name
            for name, queries in RESEARCH_ANALYSIS_FIELD_QUERIES.items()
            if query in queries
        )
        chinese = {
            "participants": "本研究选取A大学68名本科二年级学生作为研究对象。",
            "intervention": "实验持续5周，每周2课时。",
            "assessmentTools": "采用学习支架设计准则量表进行测量。",
            "mainFindings": "结果表明实验组表现显著提升。",
            "limitations": "本研究样本来自单一大学，迁移仍有限。",
        }.get(field, f"{field} 对应的论文证据")
        return [
            ProjectKnowledgeSource(
                content=chinese,
                project_id=project_id,
                filename="中文实证研究.pdf",
                file_id=file_id,
                chunk_id=f"chunk-{field}",
                chunk_index=len(field),
                score=0.9,
            )
        ]


def test_chinese_field_aware_evidence_is_scoped_and_separated() -> None:
    bundle = asyncio.run(
        ResearchAnalysisEvidenceCollector(FieldKnowledge()).collect(  # type: ignore[arg-type]
            project_id=7, file_id=11, max_chunks=20, max_chars=12000
        )
    )

    assert "68名本科二年级学生" in bundle.field_sources["participants"][0].content
    assert "实验持续5周" in bundle.field_sources["intervention"][0].content
    assert "量表" in bundle.field_sources["assessmentTools"][0].content
    assert "显著提升" in bundle.field_sources["mainFindings"][0].content
    assert "单一大学" in bundle.field_sources["limitations"][0].content
    assert "[FIELD EVIDENCE: participants]" in bundle.prompt_context
    assert "[CHUNK REGISTRY]" in bundle.prompt_context
    assert all(source.file_id == 11 for source in bundle.unique_sources)


class SequenceProvider:
    def __init__(self, results):
        self.results = list(results)
        self.requests = []

    async def analyze_research(self, request):
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(provider="general-spark", data=result)

    async def supplement_research_analysis(self, request):
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(provider="general-spark", data=result)


class RecordingEvidenceCollector(ResearchAnalysisEvidenceCollector):
    def __init__(self):
        super().__init__(FieldKnowledge())  # type: ignore[arg-type]
        self.calls = []

    async def collect(self, **kwargs):
        self.calls.append(kwargs)
        return await super().collect(**kwargs)

def complete_analysis(**updates) -> ResearchAnalysisResult:
    values = dict(
        research_subjects=["68名本科二年级学生"],
        research_topics=["智能化学习支架"],
        ai_literacy_dimensions=["AI_COGNITION"],
        teaching_strategies=["智能化学习支架"],
        intervention_duration="5周",
        assessment_tools=["学习支架设计准则量表"],
        main_findings=["实验组表现显著提升"],
        limitations=["单一大学样本"],
        teaching_implications="提供分层支架",
    )
    values.update(updates)
    return ResearchAnalysisResult(**values)


def test_targeted_supplement_runs_once_and_merges_only_missing_fields() -> None:
    batch_a = ResearchAnalysisPatch(
        research_subjects=["68名本科二年级学生"],
        research_topics=["智能化学习支架"],
        intervention_duration="5周",
    )
    batch_b = ResearchAnalysisPatch(
        ai_literacy_dimensions=["AI_COGNITION"],
        teaching_strategies=["智能化学习支架"],
        assessment_tools=["学习支架设计准则量表"],
    )
    batch_c = ResearchAnalysisPatch(
        main_findings=["实验组表现显著提升"],
        limitations=["单一大学样本"],
        teaching_implications="提供分层支架",
    )
    provider = SequenceProvider([batch_a, batch_b, batch_c])
    collector = RecordingEvidenceCollector()
    service = ResearchAnalysisExtractionService(
        provider,  # type: ignore[arg-type]
        collector,
    )

    result = asyncio.run(
        service.extract(
            project_id=7,
            resource_id=11,
            project_title="项目",
            project_topic="智能化学习支架",
        )
    )

    assert len(provider.requests) == 3
    assert [request.missing_fields for request in provider.requests] == [
        ["participants", "researchTopic", "intervention"],
        ["aiLiteracyDimensions", "teachingStrategies", "assessmentTools"],
        ["mainFindings", "limitations", "teachingImplications"],
    ]
    assert result.analysis.research_subjects == ["68名本科二年级学生"]
    assert result.analysis.assessment_tools == ["学习支架设计准则量表"]
    assert result.analysis.main_findings == batch_c.main_findings
    assert result.diagnostics.supplement_attempted is False
    assert len(collector.calls) == 3
    assert all(call["top_k"] == 2 for call in collector.calls)
    assert all(call["max_chunks"] == 4 for call in collector.calls)
    assert all(call["max_chars"] == 4500 for call in collector.calls)


def test_supplement_still_missing_remains_incomplete_without_looping() -> None:
    provider = SequenceProvider([ResearchAnalysisPatch() for _ in range(12)])
    collector = RecordingEvidenceCollector()
    service = ResearchAnalysisExtractionService(
        provider,  # type: ignore[arg-type]
        collector,
    )
    result = asyncio.run(
        service.extract(
            project_id=7, resource_id=11, project_title=None, project_topic=None
        )
    )
    readiness = EvidenceReadinessService.evaluate(
        result.analysis,
        EvidenceReadinessService.source_metadata_from_knowledge_base(),
    )
    assert len(provider.requests) == 12
    assert all(
        request.analysis_field is not None and len(request.missing_fields) == 1
        for request in provider.requests[3:]
    )
    assert all(call["top_k"] == 2 for call in collector.calls[3:])
    assert all(call["max_chunks"] == 2 for call in collector.calls[3:])
    assert all(call["max_chars"] == 2500 for call in collector.calls[3:])
    assert readiness.readiness_status == "INCOMPLETE"
    assert "researchContext" in readiness.missing_required_fields


def test_structured_provider_failure_is_propagated_for_failed_status_mapping() -> None:
    provider = SequenceProvider([
        SparkTimeoutError("timeout-a"),
        SparkTimeoutError("timeout-b"),
        SparkTimeoutError("timeout-c"),
    ])
    service = ResearchAnalysisExtractionService(
        provider,  # type: ignore[arg-type]
        ResearchAnalysisEvidenceCollector(FieldKnowledge()),  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError, match="All research analysis batches failed"):
        asyncio.run(
            service.extract(
                project_id=7, resource_id=11, project_title=None, project_topic=None
            )
        )


def test_failed_model_probe_stops_before_retrieval_and_batches() -> None:
    class ProbeFailProvider(SequenceProvider):
        async def probe_research_analysis_model(self, **_kwargs):
            raise SparkOutputLengthError("probe exhausted", reasoning_tokens=255)

    provider = ProbeFailProvider([])
    collector = RecordingEvidenceCollector()
    service = ResearchAnalysisExtractionService(provider, collector)  # type: ignore[arg-type]

    with pytest.raises(SparkOutputLengthError, match="probe exhausted"):
        asyncio.run(service.extract(
            project_id=7, resource_id=11, project_title=None, project_topic=None,
        ))

    assert provider.requests == []
    assert collector.calls == []


def test_research_analysis_model_probe_uses_tiny_independent_request(monkeypatch) -> None:
    class ProbeClient:
        def __init__(self):
            self.kwargs = None

        async def chat_json(self, _messages, **kwargs):
            self.kwargs = kwargs
            return {"ok": True}

    monkeypatch.setattr(settings, "spark_research_analysis_model_id", "spark-x2.5-1.7b")
    client = ProbeClient()
    asyncio.run(SparkResearchAssistant(client=client).probe_research_analysis_model(  # type: ignore[arg-type]
        project_id=7, resource_id=11,
    ))

    assert client.kwargs["max_tokens"] == 256
    assert client.kwargs["model_id"] == "spark-x2.5-1.7b"
    assert client.kwargs["performance_context"]["reasoning_exhaustion_ratio"] == 0.90


def test_one_failed_batch_keeps_other_batch_results() -> None:
    provider = SequenceProvider([
        ResearchAnalysisPatch(
            research_subjects=["Grade 5 students"],
            research_topics=["AI literacy"],
            intervention_duration="4 weeks",
        ),
        SparkTimeoutError("batch-b exhausted reasoning tokens"),
        ResearchAnalysisPatch(
            main_findings=["Verification improved"],
            limitations=["Single-school sample"],
            teaching_implications="Use guided practice",
        ),
        ResearchAnalysisPatch(ai_literacy_dimensions=["AI knowledge"]),
        ResearchAnalysisPatch(teaching_strategies=["Guided practice"]),
        ResearchAnalysisPatch(assessment_tools=["Questionnaire"]),
    ])
    service = ResearchAnalysisExtractionService(
        provider,  # type: ignore[arg-type]
        ResearchAnalysisEvidenceCollector(FieldKnowledge()),  # type: ignore[arg-type]
    )

    result = asyncio.run(service.extract(
        project_id=7, resource_id=11, project_title=None, project_topic=None,
    ))

    assert result.analysis.research_subjects == ["Grade 5 students"]
    assert result.analysis.ai_literacy_dimensions == ["AI knowledge"]
    assert result.analysis.teaching_strategies == ["Guided practice"]
    assert result.analysis.assessment_tools == ["Questionnaire"]
    assert result.analysis.main_findings == ["Verification improved"]
    assert result.diagnostics.failed_batches == ["B"]


class JsonClient:
    def __init__(self, source_excerpt: str):
        self.source_excerpt = source_excerpt

    async def chat_json(self, _messages, *, repair=False, **_kwargs):
        return {
            "researchSubjects": ["68 undergraduate students"],
            "mainFindings": ["The intervention improved outcomes"],
            "sourceExcerpt": self.source_excerpt,
        }


@pytest.mark.parametrize(
    ("source", "excerpt", "expected"),
    [
        ("68 participants were recruited", "68 participants were recruited", "68 participants were recruited"),
        ("68 participants\nwere recruited", "68 participants were recruited", "68 participants were recruited"),
        ("68 undergraduate students participated", "The study involved sixty-eight undergraduates", None),
    ],
)
def test_source_excerpt_validation_is_non_blocking(source, excerpt, expected) -> None:
    response = asyncio.run(
        SparkResearchAssistant(client=JsonClient(excerpt)).analyze_research(  # type: ignore[arg-type]
            ResearchAnalysisRequest(resource_id=11, analysis_evidence=source)
        )
    )
    assert response.data.source_excerpt == expected
    assert response.data.research_subjects == ["68 undergraduate students"]


def test_supplement_failure_preserves_first_pass_and_ready_generation() -> None:
    provider = SequenceProvider([
        ResearchAnalysisPatch(research_subjects=["students"]),
        SparkContractError("batch-b contract mismatch"),
        ResearchAnalysisPatch(main_findings=["supported finding"]),
    ])
    result = asyncio.run(
        ResearchAnalysisExtractionService(
            provider, ResearchAnalysisEvidenceCollector(FieldKnowledge())  # type: ignore[arg-type]
        ).extract(project_id=7, resource_id=11, project_title=None, project_topic=None)
    )
    assert result.generation_status == "READY"
    assert result.analysis.research_subjects == ["students"]
    assert result.analysis.main_findings == ["supported finding"]
    assert result.diagnostics.supplement_failed is True


def test_supplement_only_fills_missing_and_degraded_result_can_make_card() -> None:
    first = complete_analysis(assessment_tools=[])
    patch = ResearchAnalysisPatch(
        research_subjects=["wrong value"], assessment_tools=["Questionnaire"]
    )
    merged = ResearchAnalysisExtractionService._merge_missing(
        first, patch, ["assessmentTools"]
    )
    assert merged.research_subjects == first.research_subjects
    assert merged.assessment_tools == ["Questionnaire"]

    readiness = EvidenceReadinessService.evaluate(
        first, EvidenceReadinessService.source_metadata_from_knowledge_base()
    )
    assert readiness.readiness_status == "READY"
    draft = EvidenceCardDraftService.map_draft(
        analysis_record=SimpleNamespace(id=91, project_id=7),
        analysis=first,
        resource=None,
    )
    assert draft.research_finding == "实验组表现显著提升"


def test_spark_supplement_contract_excludes_excerpt_and_full_analysis() -> None:
    class SupplementClient:
        def __init__(self):
            self.messages = None
            self.kwargs = None

        async def chat_json(self, messages, *, repair=False, **kwargs):
            self.messages = messages
            self.kwargs = kwargs
            return {"assessmentTools": ["Questionnaire"]}

    client = SupplementClient()
    response = asyncio.run(
        SparkResearchAssistant(client=client).supplement_research_analysis(  # type: ignore[arg-type]
            ResearchAnalysisSupplementRequest(
                resource_id=11,
                analysis_batch="B",
                analysis_field="assessmentTools",
                missing_fields=["assessmentTools"],
                analysis_evidence="[FIELD EVIDENCE: assessmentTools]\nchunk ids: c1",
                current_analysis=complete_analysis(assessment_tools=[]),
            )
        )
    )
    prompt = client.messages[-1]["content"]
    assert response.data.assessment_tools == ["Questionnaire"]
    assert '"outputTemplate"' in prompt
    assert '"assessmentTools"' in prompt
    assert '"aiLiteracyDimensions"' not in prompt
    assert '"teachingStrategies"' not in prompt
    assert '"researchSubjects"' not in prompt
    assert '"sourceExcerpt"' not in prompt
    assert '"resultSchema"' not in prompt
    assert client.kwargs["max_tokens"] == 2048


def test_research_batch_normalizes_aliases_and_drops_extra_fields_without_repair() -> None:
    class NormalizeClient:
        def __init__(self):
            self.calls = 0

        async def chat_json(self, _messages, **_kwargs):
            self.calls += 1
            return {
                "participants": "Grade 5 students",
                "researchTopic": "AI literacy",
                "intervention": "4 weeks",
                "mainFindings": ["must be dropped from batch A"],
            }

    client = NormalizeClient()
    response = asyncio.run(
        SparkResearchAssistant(client=client).supplement_research_analysis(  # type: ignore[arg-type]
            ResearchAnalysisSupplementRequest(
                resource_id=11,
                analysis_batch="A",
                missing_fields=["participants", "researchTopic", "intervention"],
                analysis_evidence="[FIELD EVIDENCE: participants]\nchunk ids: c1",
                current_analysis=ResearchAnalysisResult(),
            )
        )
    )

    assert client.calls == 1
    assert response.data.research_subjects == ["Grade 5 students"]
    assert response.data.research_topics == ["AI literacy"]
    assert response.data.intervention_duration == "4 weeks"
    assert response.data.main_findings is None


class ExtractionDb:
    def commit(self):
        pass

    def rollback(self):
        pass


class ExtractionRepository:
    def __init__(self, resource):
        self.resource = resource

    def get_owned_active_resource(self, **kwargs):
        return self.resource

    def mark_text_extracting(self, resource):
        resource.processing_status = "TEXT_EXTRACTING"

    def mark_text_extracted(self, resource, *, extracted_text):
        resource.processing_status = "TEXT_EXTRACTED"
        resource.extracted_text = extracted_text

    def mark_failed(self, resource, *, error_message):
        resource.processing_status = "FAILED"


def resource_record():
    return SimpleNamespace(
        id=11,
        project_id=7,
        processing_status="UPLOADED",
        extracted_text=None,
        storage_key="paper.pdf",
        media_type="application/pdf",
        original_filename="paper.pdf",
        index_status="pending",
    )


def test_pdf_extraction_prefers_pymupdf4llm_markdown(caplog) -> None:
    class Parser:
        def parse_pdf_to_markdown(self, **kwargs):
            return "## 2 研究方法\n\n### 2.1 研究对象\n68名学生"

        def parse(self, **kwargs):
            raise AssertionError("fallback must not run")

    resource = resource_record()
    service = ResearchTextExtractionService(ExtractionDb(), Parser())  # type: ignore[arg-type]
    service.repository = ExtractionRepository(resource)  # type: ignore[assignment]
    service._resolve_file_path = lambda _: Path("paper.pdf")  # type: ignore[method-assign]
    with caplog.at_level("INFO"):
        result = service.extract_text(current_user_id=1, resource_id=11)
    assert result["extractedText"].startswith("## 2 研究方法")
    assert "parser_engine=PYMUPDF4LLM" in caplog.text


def test_pdf_extraction_falls_back_to_pypdf_plain_text(caplog) -> None:
    class Parser:
        def parse_pdf_to_markdown(self, **kwargs):
            raise DocumentParsingError("converter failed")

        def parse(self, **kwargs):
            return "本研究选取68名学生。结果表明显著提升。"

    resource = resource_record()
    service = ResearchTextExtractionService(ExtractionDb(), Parser())  # type: ignore[arg-type]
    service.repository = ExtractionRepository(resource)  # type: ignore[assignment]
    service._resolve_file_path = lambda _: Path("paper.pdf")  # type: ignore[method-assign]
    with caplog.at_level("INFO"):
        result = service.extract_text(current_user_id=1, resource_id=11)
    assert result["extractedText"].startswith("本研究")
    assert "parser_engine=PYPDF_FALLBACK" in caplog.text
