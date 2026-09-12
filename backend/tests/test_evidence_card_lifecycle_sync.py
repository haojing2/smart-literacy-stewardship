from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.evidence_card import EvidenceCard
from app.models.research import ResearchAnalysis, ResearchChatSession, ResearchResource
from app.models.user import SysUser
from app.schemas.research_assistant import (
    EvidenceCardInterpretation,
    ResearchAnalysisEditRequest,
    ResearchAnalysisResult,
    ResearchChatResponse,
    ResearchChatResult,
)
from app.services.evidence_card_draft_service import EvidenceCardDraftService
from app.services.project_knowledge_service import ProjectKnowledgeSource
from app.services.research_analysis_service import ResearchAnalysisService
from app.services.research_chat_service import ResearchChatService


def ready_analysis() -> ResearchAnalysisResult:
    return ResearchAnalysisResult(
        research_subjects=["Grade 5 students"],
        research_topics=["AI verification"],
        ai_literacy_dimensions=["INFORMATION_VERIFICATION"],
        teaching_strategies=["Compare multiple sources"],
        intervention_duration="8 weeks",
        assessment_tools=["Performance rubric"],
        main_findings=["Verification performance improved"],
        limitations=["Single-school sample"],
        source_excerpt="Grounded source excerpt.",
    )


def create_workspace(
    db: Session, teacher: SysUser, *, analysis: ResearchAnalysisResult | None = None
) -> tuple[CourseProject, ResearchResource, ResearchChatSession, ResearchAnalysis]:
    project = CourseProject(
        user_id=teacher.id,
        title="Evidence lifecycle project",
        topic="AI verification",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.flush()
    resource = ResearchResource(
        project_id=project.id,
        user_id=teacher.id,
        original_filename="study.pdf",
        storage_key=f"{teacher.id}/{project.id}/study.pdf",
        media_type="application/pdf",
        size_bytes=2048,
        sha256="d" * 64,
        processing_status="TEXT_EXTRACTED",
        extracted_text="Grounded source excerpt.",
        index_status="ready",
    )
    db.add(resource)
    db.flush()
    session = ResearchChatSession(
        user_id=teacher.id,
        project_id=project.id,
        resource_id=resource.id,
        title="Evidence lifecycle",
        status="ACTIVE",
    )
    db.add(session)
    db.flush()
    record = ResearchAnalysis(
        project_id=project.id,
        resource_id=resource.id,
        version=1,
        structured_data_json=(analysis or ready_analysis()).model_dump(
            mode="json", by_alias=False
        ),
        field_sources_json={},
        status="VALIDATED",
    )
    db.add(record)
    db.commit()
    return project, resource, session, record


def test_project_chat_without_ready_resources_never_calls_provider(
    db: Session, teacher: SysUser
) -> None:
    project = CourseProject(
        user_id=teacher.id,
        title="Empty research project",
        topic="AI literacy",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.flush()
    session = ResearchChatSession(
        user_id=teacher.id,
        project_id=project.id,
        resource_id=None,
        title="Project research chat",
        status="ACTIVE",
    )
    db.add(session)
    db.flush()
    db.add(ResearchAnalysis(
        project_id=project.id,
        session_id=session.id,
        resource_id=None,
        version=1,
        structured_data_json=ResearchAnalysisResult().model_dump(mode="json"),
        field_sources_json={},
        status="VALIDATED",
    ))
    db.commit()

    class Provider:
        calls = 0

        async def chat(self, _request):
            self.calls += 1
            raise AssertionError("Provider must not be called without project-local evidence")

    provider = Provider()
    response = asyncio.run(ResearchChatService(db, provider).send_message(  # type: ignore[arg-type]
        current_user_id=teacher.id,
        session_id=session.id,
        content="How many papers are in this project?",
    ))

    assert provider.calls == 0
    assert response.assistant_message.content == "当前项目尚未添加可检索的研究资源，请先上传研究论文。"
    assert response.analysis_patch is None


def add_analysis(
    db: Session,
    *,
    project_id: int,
    resource_id: int,
    version: int,
    analysis: ResearchAnalysisResult,
) -> ResearchAnalysis:
    record = ResearchAnalysis(
        project_id=project_id,
        resource_id=resource_id,
        version=version,
        structured_data_json=analysis.model_dump(mode="json", by_alias=False),
        field_sources_json={},
        status="VALIDATED",
    )
    db.add(record)
    db.commit()
    return record


def test_ready_to_ready_creates_current_card_and_keeps_stale_protection(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project, resource, session, first_analysis = create_workspace(db, teacher)
    service = EvidenceCardDraftService(db)
    first = service.ensure_current_draft(
        current_user_id=teacher.id,
        session_id=session.id,
        analysis_id=first_analysis.id,
    )
    second_analysis = add_analysis(
        db,
        project_id=project.id,
        resource_id=resource.id,
        version=2,
        analysis=ready_analysis(),
    )
    second = service.ensure_current_draft(
        current_user_id=teacher.id,
        session_id=session.id,
        analysis_id=second_analysis.id,
    )

    assert first.created is True and second.created is True
    assert first.draft is not None and second.draft is not None
    assert second.draft.evidence_card_id != first.draft.evidence_card_id
    assert second.draft.research_analysis_id == second_analysis.id
    db.refresh(session)
    assert session.evidence_card_id == second.draft.evidence_card_id

    current_response = client.post(
        f"/api/v1/evidence-cards/{second.draft.evidence_card_id}/confirm",
        headers=auth_headers,
    )
    assert current_response.status_code == 200
    stale_response = client.post(
        f"/api/v1/evidence-cards/{first.draft.evidence_card_id}/confirm",
        headers=auth_headers,
    )
    assert stale_response.status_code == 409
    assert stale_response.json()["code"] == 40906


def test_same_analysis_reuses_current_card_without_creating_another(
    db: Session, teacher: SysUser
) -> None:
    _, _, session, analysis = create_workspace(db, teacher)
    service = EvidenceCardDraftService(db)
    first = service.ensure_current_draft(
        current_user_id=teacher.id, session_id=session.id, analysis_id=analysis.id
    )
    repeated = service.ensure_current_draft(
        current_user_id=teacher.id, session_id=session.id, analysis_id=analysis.id
    )

    assert first.draft is not None and repeated.draft is not None
    assert repeated.created is False
    assert repeated.action == "REUSE"
    assert repeated.draft.evidence_card_id == first.draft.evidence_card_id
    assert db.scalar(select(func.count()).select_from(EvidenceCard)) == 1


def test_agent_ready_patch_replaces_current_card_and_no_patch_reuses_it(
    db: Session, teacher: SysUser
) -> None:
    _, _, session, first_analysis = create_workspace(db, teacher)
    first = EvidenceCardDraftService(db).ensure_current_draft(
        current_user_id=teacher.id,
        session_id=session.id,
        analysis_id=first_analysis.id,
    )

    class Knowledge:
        async def search_resource(self, **kwargs):
            return [ProjectKnowledgeSource(
                content="The paper studies AI verification principles.",
                project_id=kwargs["project_id"], filename="paper.pdf",
                file_id=kwargs["file_id"], chunk_id="evidence-1",
                chunk_index=0, score=0.9,
            )]

    class Rewriter:
        async def rewrite(self, **_kwargs):
            return "AI verification principles"

    class Provider:
        calls = 0

        async def chat(self, _request):
            self.calls += 1
            return ResearchChatResponse(
                provider="mock",
                request_fingerprint=str(self.calls) * 64,
                data=ResearchChatResult(
                    message="Updated analysis" if self.calls == 1 else "No change",
                    analysisPatch=(
                        {"researchTopics": ["AI verification principles"]}
                        if self.calls == 1
                        else None
                    ),
                    evidenceInterpretations=(
                        [EvidenceCardInterpretation(
                            chunkId="evidence-1", evidenceMeaning="The paper states the topic.",
                            relationToQuestion="Directly answers the question.",
                            synthesis="AI verification is the research topic.",
                        )]
                        if self.calls == 1 else []
                    ),
                ),
            )

    provider = Provider()
    service = ResearchChatService(
        db,
        provider,  # type: ignore[arg-type]
        Knowledge(),  # type: ignore[arg-type]
        Rewriter(),  # type: ignore[arg-type]
    )
    patched = asyncio.run(
        service.send_message(
            current_user_id=teacher.id,
            session_id=session.id,
            content="Update the research topic",
        )
    )
    unchanged = asyncio.run(
        service.send_message(
            current_user_id=teacher.id,
            session_id=session.id,
            content="Explain that result",
        )
    )

    assert first.draft is not None
    assert patched.evidence_draft_generated is True
    assert patched.field_sources["researchTopics"] == "AI_CHAT"
    assert patched.version == first_analysis.version + 1
    assert patched.evidence_card_id is not None
    assert patched.evidence_card_id != first.draft.evidence_card_id
    current = db.get(EvidenceCard, patched.evidence_card_id)
    assert current is not None and current.research_analysis_id != first_analysis.id
    assert unchanged.evidence_draft_generated is False
    assert unchanged.evidence_card_id == patched.evidence_card_id
    assert db.scalar(
        select(func.count()).select_from(EvidenceCard).where(
            EvidenceCard.source_chunk_id.is_(None)
        )
    ) == 2


def test_teacher_update_creates_and_binds_latest_analysis_card(
    db: Session, teacher: SysUser
) -> None:
    _, _, session, first_analysis = create_workspace(db, teacher)
    first = EvidenceCardDraftService(db).ensure_current_draft(
        current_user_id=teacher.id,
        session_id=session.id,
        analysis_id=first_analysis.id,
    )
    response = ResearchAnalysisService(db).update_analysis(
        current_user_id=teacher.id,
        session_id=session.id,
        request=ResearchAnalysisEditRequest(
            participants=["Grade 5 students"],
            researchTopic="AI verification principles",
            aiLiteracyDimensions=["INFORMATION_VERIFICATION"],
            teachingStrategies=["Compare multiple sources"],
            intervention="8 weeks",
            assessmentTools=["Performance rubric"],
            mainFindings=["Verification performance improved"],
            limitations=["Single-school sample"],
        ),
    )

    assert response.version == 2
    assert response.evidence_draft_generated is True
    assert response.evidence_card_id is not None
    assert first.draft is not None
    assert response.evidence_card_id != first.draft.evidence_card_id
    current = db.get(EvidenceCard, response.evidence_card_id)
    assert current is not None and current.research_analysis_id == response.analysis_id
    db.refresh(session)
    assert session.evidence_card_id == current.id


def test_incomplete_latest_analysis_clears_binding_without_deleting_history(
    db: Session, teacher: SysUser
) -> None:
    project, resource, session, first_analysis = create_workspace(db, teacher)
    service = EvidenceCardDraftService(db)
    first = service.ensure_current_draft(
        current_user_id=teacher.id,
        session_id=session.id,
        analysis_id=first_analysis.id,
    )
    incomplete = ready_analysis().model_copy(update={"main_findings": []})
    second_analysis = add_analysis(
        db,
        project_id=project.id,
        resource_id=resource.id,
        version=2,
        analysis=incomplete,
    )
    result = service.ensure_current_draft(
        current_user_id=teacher.id,
        session_id=session.id,
        analysis_id=second_analysis.id,
    )

    assert result.draft is None
    assert result.created is False
    assert result.action == "CLEAR_STALE"
    db.refresh(session)
    assert session.evidence_card_id is None
    assert first.draft is not None
    assert db.get(EvidenceCard, first.draft.evidence_card_id) is not None


def test_get_session_creates_and_binds_missing_card_for_ready_latest_analysis(
    db: Session, teacher: SysUser
) -> None:
    _, _, session, analysis = create_workspace(db, teacher)

    response = ResearchChatService(db, object()).get_session(  # type: ignore[arg-type]
        current_user_id=teacher.id,
        session_id=session.id,
    )

    assert response.evidence_card_id is not None
    card = db.get(EvidenceCard, response.evidence_card_id)
    assert card is not None
    assert card.research_analysis_id == analysis.id
    db.refresh(session)
    assert session.evidence_card_id == card.id


def test_get_session_reuses_analysis_card_when_binding_is_stale(
    db: Session, teacher: SysUser
) -> None:
    _, _, session, analysis = create_workspace(db, teacher)
    synchronized = EvidenceCardDraftService(db).ensure_current_draft(
        current_user_id=teacher.id,
        session_id=session.id,
        analysis_id=analysis.id,
    )
    assert synchronized.draft is not None
    expected_card_id = synchronized.draft.evidence_card_id
    session.evidence_card_id = None
    db.commit()

    response = ResearchChatService(db, object()).get_session(  # type: ignore[arg-type]
        current_user_id=teacher.id,
        session_id=session.id,
    )

    assert response.evidence_card_id == expected_card_id
    assert db.scalar(select(func.count()).select_from(EvidenceCard).where(
        EvidenceCard.research_analysis_id == analysis.id,
        EvidenceCard.source_chunk_id.is_(None),
    )) == 1


def test_retrieval_card_never_becomes_synthesized_response_card(
    db: Session, teacher: SysUser
) -> None:
    project, resource, session, analysis = create_workspace(
        db,
        teacher,
        analysis=ready_analysis().model_copy(update={"main_findings": []}),
    )
    source = ProjectKnowledgeSource(
        project_id=project.id,
        content="Retrieved source chunk.",
        filename=resource.original_filename,
        file_id=resource.id,
        chunk_id="e" * 64,
        chunk_index=1,
        score=0.91,
    )

    class Knowledge:
        async def search_resource(self, **_kwargs):
            return [source]

    class Provider:
        async def chat(self, _request):
            return ResearchChatResponse(
                provider="mock",
                request_fingerprint="a" * 64,
                data=ResearchChatResult(
                    message="Answer grounded in the retrieved chunk.",
                    analysis_patch=None,
                    evidence_interpretations=[
                        EvidenceCardInterpretation(
                            chunkId=source.chunk_id,
                            evidenceMeaning="Relevant evidence",
                            relationToQuestion="Directly relevant",
                            synthesis="Use cautiously",
                        )
                    ],
                ),
            )

    response = asyncio.run(
        ResearchChatService(
            db,
            Provider(),  # type: ignore[arg-type]
            Knowledge(),  # type: ignore[arg-type]
        ).send_message(
            current_user_id=teacher.id,
            session_id=session.id,
            content="What does the paper report?",
        )
    )

    assert response.evidence_card_id is None
    assert response.evidence_draft_generated is False
    retrieval_card = db.scalar(
        select(EvidenceCard).where(EvidenceCard.source_chunk_id == source.chunk_id)
    )
    assert retrieval_card is not None
    db.refresh(session)
    assert session.evidence_card_id is None
    assert analysis.id == retrieval_card.research_analysis_id
