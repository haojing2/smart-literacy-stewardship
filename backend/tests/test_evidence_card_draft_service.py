from __future__ import annotations

import inspect

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.evidence_card import EvidenceCard
from app.models.research import ResearchAnalysis, ResearchChatMessage, ResearchChatSession, ResearchResource
from app.models.user import SysUser
from app.schemas.research_assistant import (
    EvidenceCardInterpretation,
    ProjectKnowledgeSourceInput,
    ResearchAnalysisResult,
)
from app.services.evidence_card_draft_service import (
    EvidenceAnalysisStaleError,
    EvidenceCardDraftService,
    EvidenceCardNotFoundError,
)
from app.services.evidence_readiness_service import EvidenceNotReadyError


def create_analysis(
    db: Session,
    user: SysUser,
    *,
    complete: bool = True,
    teaching_implications: str | None = None,
) -> tuple[CourseProject, ResearchResource, ResearchAnalysis]:
    project = CourseProject(
        user_id=user.id,
        title="Evidence mapping project",
        topic="AI information verification",
        project_type="NEW_TOPIC",
        workflow_state="CONTEXT_READY",
        stale_sections_json=[],
    )
    db.add(project)
    db.flush()
    resource = ResearchResource(
        project_id=project.id,
        user_id=user.id,
        original_filename="study.pdf",
        storage_key=f"{user.id}/{project.id}/study.pdf",
        media_type="application/pdf",
        size_bytes=2048,
        sha256="b" * 64,
        processing_status="TEXT_EXTRACTED",
        extracted_text="Complete source text",
    )
    db.add(resource)
    db.flush()
    data = ResearchAnalysisResult(
        research_subjects=["Grade 5 students"] if complete else [],
        research_topics=["AI verification"],
        ai_literacy_dimensions=["INFORMATION_VERIFICATION"],
        teaching_strategies=["Compare multiple sources"] if complete else [],
        intervention_duration="8 weeks",
        assessment_tools=["Performance rubric"],
        main_findings=["Verification performance improved"] if complete else [],
        limitations=["Single-school sample"],
        teaching_implications=teaching_implications,
        source_excerpt="Grounded excerpt from the source.",
    )
    analysis = ResearchAnalysis(
        resource_id=resource.id,
        version=1,
        structured_data_json=data.model_dump(mode="json", by_alias=False),
        field_sources_json={},
        status="VALIDATED",
    )
    db.add(analysis)
    db.commit()
    return project, resource, analysis


def test_mapping_is_deterministic_and_does_not_invent_teaching_implications(
    db: Session,
    teacher: SysUser,
) -> None:
    _, resource, analysis_record = create_analysis(db, teacher)
    analysis = ResearchAnalysisResult.model_validate(
        analysis_record.structured_data_json
    )

    first = EvidenceCardDraftService.map_draft(
        analysis_record=analysis_record,
        analysis=analysis,
        resource=resource,
    )
    second = EvidenceCardDraftService.map_draft(
        analysis_record=analysis_record,
        analysis=analysis,
        resource=resource,
    )

    assert first == second
    assert first.research_finding == "Verification performance improved"
    assert first.applicable_audience == "Grade 5 students"
    assert first.recommended_strategies == ["Compare multiple sources"]
    assert first.implementation_conditions == ["8 weeks"]
    assert first.limitations == "Single-school sample"
    assert first.teaching_implications == ""
    assert first.source.original_filename == "study.pdf"
    assert first.source.sha256 == "b" * 64
    assert first.card_status == "DRAFT"


def test_generate_persists_one_draft_and_confirmation_is_teacher_only(
    db: Session,
    teacher: SysUser,
) -> None:
    _, resource, analysis = create_analysis(
        db,
        teacher,
        teaching_implications="Use source comparison in classroom discussion.",
    )
    service = EvidenceCardDraftService(db)

    first = service.generate_draft(
        current_user_id=teacher.id,
        analysis_id=analysis.id,
    )
    second = service.generate_draft(
        current_user_id=teacher.id,
        analysis_id=analysis.id,
    )

    assert first.evidence_card_id == second.evidence_card_id
    assert first.card_status == "DRAFT"
    assert first.teaching_implications == (
        "Use source comparison in classroom discussion."
    )
    assert first.source.resource_id == resource.id
    assert db.scalar(select(func.count()).select_from(EvidenceCard)) == 1

    confirmed = service.confirm_draft(
        current_user_id=teacher.id,
        evidence_card_id=first.evidence_card_id,
    )
    assert confirmed.card_status == "CONFIRMED"
    assert confirmed.confirmed_by == teacher.id
    assert confirmed.confirmed_at is not None


def test_incomplete_analysis_cannot_generate_draft(
    db: Session,
    teacher: SysUser,
) -> None:
    _, _, analysis = create_analysis(db, teacher, complete=False)

    try:
        EvidenceCardDraftService(db).generate_draft(
            current_user_id=teacher.id,
            analysis_id=analysis.id,
        )
    except EvidenceNotReadyError as exc:
        assert exc.readiness.readiness_status == "INCOMPLETE"
    else:
        raise AssertionError("Incomplete analysis unexpectedly generated a draft")


def test_foreign_teacher_cannot_generate_or_confirm_card(
    db: Session,
    teacher: SysUser,
    other: SysUser,
) -> None:
    _, _, analysis = create_analysis(db, teacher)
    service = EvidenceCardDraftService(db)

    try:
        service.generate_draft(
            current_user_id=other.id,
            analysis_id=analysis.id,
        )
    except EvidenceCardNotFoundError:
        pass
    else:
        raise AssertionError("Foreign teacher unexpectedly generated a draft")

    draft = service.generate_draft(
        current_user_id=teacher.id,
        analysis_id=analysis.id,
    )
    try:
        service.confirm_draft(
            current_user_id=other.id,
            evidence_card_id=draft.evidence_card_id,
        )
    except EvidenceCardNotFoundError:
        pass
    else:
        raise AssertionError("Foreign teacher unexpectedly confirmed a draft")


def test_draft_service_does_not_depend_on_any_assistant_provider() -> None:
    module = __import__(
        "app.services.evidence_card_draft_service",
        fromlist=["EvidenceCardDraftService"],
    )
    source = inspect.getsource(module)
    assert "ResearchAssistantProvider" not in source
    assert "MockResearchAssistant" not in source
    assert "Spark" not in source


def test_stale_draft_cannot_be_confirmed(
    db: Session,
    teacher: SysUser,
) -> None:
    _, resource, analysis = create_analysis(db, teacher)
    service = EvidenceCardDraftService(db)
    draft = service.generate_draft(
        current_user_id=teacher.id,
        analysis_id=analysis.id,
    )
    newer = ResearchAnalysis(
        resource_id=resource.id,
        version=2,
        structured_data_json=analysis.structured_data_json,
        field_sources_json={},
        status="VALIDATED",
    )
    db.add(newer)
    db.commit()

    try:
        service.confirm_draft(
            current_user_id=teacher.id,
            evidence_card_id=draft.evidence_card_id,
        )
    except EvidenceAnalysisStaleError:
        pass
    else:
        raise AssertionError("Stale draft unexpectedly became confirmed")


def test_retrieval_draft_uses_backend_chunk_provenance_and_is_idempotent(
    db: Session,
    teacher: SysUser,
) -> None:
    project, resource, analysis = create_analysis(db, teacher)
    session = ResearchChatSession(
        user_id=teacher.id,
        project_id=project.id,
        resource_id=resource.id,
        title="Evidence retrieval chat",
        status="ACTIVE",
    )
    db.add(session)
    db.flush()
    message = ResearchChatMessage(
        session_id=session.id,
        role="ASSISTANT",
        sequence_no=1,
        content="Assistant explanation",
    )
    db.add(message)
    db.commit()

    source = ProjectKnowledgeSourceInput(
        project_id=project.id,
        content="The exact retrieved chunk text.",
        filename="study.pdf",
        file_id=resource.id,
        chunk_id="c" * 64,
        chunk_index=2,
        score=0.87,
    )
    interpretation = EvidenceCardInterpretation(
        chunk_id=source.chunk_id,
        evidence_meaning="The source supports the intervention.",
        relation_to_question="It addresses the teacher's current question.",
        synthesis="Use the finding cautiously in the current course design.",
    )
    service = EvidenceCardDraftService(db)
    first = service.generate_retrieval_drafts(
        analysis=analysis,
        assistant_message_id=message.id,
        sources=[source],
        interpretations=[interpretation],
    )
    repeated = service.generate_retrieval_drafts(
        analysis=analysis,
        assistant_message_id=message.id,
        sources=[source],
        interpretations=[interpretation],
    )

    assert len(first) == 1
    assert repeated == []
    card = first[0]
    assert card.source_document == source.filename
    assert card.source_file_id == source.file_id
    assert card.source_chunk_id == source.chunk_id
    assert card.source_text == source.content
    assert card.source_retrieval_score == source.score
    assert card.source_message_id == message.id
    assert card.source_page is None
    assert card.main_finding == interpretation.evidence_meaning
    assert card.teaching_implication == interpretation.relation_to_question
    assert card.search_text == interpretation.synthesis
