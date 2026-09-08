from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.evidence_card import EvidenceCard
from app.models.research import ResearchAnalysis, ResearchResource


class EvidenceCardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_owned_analysis(
        self,
        *,
        analysis_id: int,
        user_id: int,
        for_update: bool = False,
    ) -> tuple[ResearchAnalysis, ResearchResource | None] | None:
        statement = (
            select(ResearchAnalysis, ResearchResource)
            .outerjoin(
                ResearchResource,
                ResearchResource.id == ResearchAnalysis.resource_id,
            )
            .join(CourseProject, CourseProject.id == ResearchAnalysis.project_id)
            .where(
                ResearchAnalysis.id == analysis_id,
                CourseProject.user_id == user_id,
                CourseProject.is_deleted.is_(False),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.execute(statement).one_or_none()

    def get_latest_analysis_id(self, *, resource_id: int | None = None, session_id: int | None = None) -> int | None:
        statement = select(ResearchAnalysis.id)
        if resource_id is not None:
            statement = statement.where(ResearchAnalysis.resource_id == resource_id)
        else:
            statement = statement.where(ResearchAnalysis.session_id == session_id)
        return self.db.scalar(
            statement
            .order_by(desc(ResearchAnalysis.version))
            .limit(1)
        )

    def get_by_analysis_id(self, *, analysis_id: int) -> EvidenceCard | None:
        """Return the legacy analysis-level card, not chunk-level retrieval cards."""
        return self.db.scalar(
            select(EvidenceCard).where(
                EvidenceCard.research_analysis_id == analysis_id,
                EvidenceCard.source_chunk_id.is_(None),
            )
        )

    def get_by_project_source_chunk(
        self, *, project_id: int, source_chunk_id: str
    ) -> EvidenceCard | None:
        return self.db.scalar(
            select(EvidenceCard).where(
                EvidenceCard.project_id == project_id,
                EvidenceCard.source_chunk_id == source_chunk_id,
            )
        )

    def get_latest_by_resource_id(self, *, resource_id: int | None = None, session_id: int | None = None) -> EvidenceCard | None:
        condition = ResearchAnalysis.resource_id == resource_id if resource_id is not None else ResearchAnalysis.session_id == session_id
        return self.db.scalar(
            select(EvidenceCard)
            .join(ResearchAnalysis, ResearchAnalysis.id == EvidenceCard.research_analysis_id)
            .where(condition, EvidenceCard.source_chunk_id.is_(None))
            .order_by(desc(EvidenceCard.id))
            .limit(1)
        )

    def list_confirmed_by_project(self, *, project_id: int) -> list[EvidenceCard]:
        return list(
            self.db.scalars(
                select(EvidenceCard)
                .join(ResearchAnalysis, ResearchAnalysis.id == EvidenceCard.research_analysis_id)
                .where(
                    ResearchAnalysis.project_id == project_id,
                    EvidenceCard.card_status == "CONFIRMED",
                )
                .order_by(desc(EvidenceCard.id))
            ).all()
        )

    def create_draft(
        self,
        *,
        analysis: ResearchAnalysis,
        resource: ResearchResource | None,
        title: str,
        topic: str | None,
        research_finding: str,
        applicable_audience: str,
        recommended_strategies: list[str],
        implementation_conditions: list[str],
        teaching_implications: str,
        limitations: str,
        source_metadata: dict[str, object],
        source_text: str,
    ) -> EvidenceCard:
        card = EvidenceCard(
            title=title,
            topic=topic,
            participants=applicable_audience,
            main_finding=research_finding,
            recommended_strategies_json=recommended_strategies,
            implementation_conditions_json=implementation_conditions,
            teaching_implication=teaching_implications or None,
            limitation=limitations or None,
            source_document=resource.original_filename if resource else "讯飞研教智联知识库",
            source_text=source_text,
            source_metadata_json=source_metadata,
            card_status="DRAFT",
            research_analysis_id=analysis.id,
            confirmed_by=None,
            confirmed_at=None,
        )
        self.db.add(card)
        self.db.flush()
        return card

    def create_retrieval_draft(
        self,
        *,
        analysis: ResearchAnalysis,
        project_id: int,
        source_file_id: int,
        source_filename: str,
        source_chunk_id: str,
        source_text: str,
        source_retrieval_score: float,
        source_message_id: int,
        evidence_meaning: str,
        relation_to_question: str,
        synthesis: str,
    ) -> EvidenceCard:
        """Persist one chunk-backed draft with immutable retrieval provenance."""
        card = EvidenceCard(
            title=f"项目资料证据：{source_filename}",
            topic=(analysis.structured_data_json.get("research_topics") or [None])[0]
            if isinstance(analysis.structured_data_json, dict)
            else None,
            main_finding=evidence_meaning,
            teaching_implication=relation_to_question,
            # search_text retains the model's combined explanation without
            # conflating it with the original retrieved excerpt.
            search_text=synthesis,
            source_document=source_filename,
            source_page=None,
            source_text=source_text,
            source_metadata_json={
                "sourceType": "UPLOADED_RESOURCE",
                "projectId": project_id,
                "fileId": source_file_id,
                "filename": source_filename,
                "chunkId": source_chunk_id,
                "retrievalScore": source_retrieval_score,
                "sourceMessageId": source_message_id,
            },
            card_status="DRAFT",
            research_analysis_id=analysis.id,
            project_id=project_id,
            source_file_id=source_file_id,
            source_chunk_id=source_chunk_id,
            source_retrieval_score=source_retrieval_score,
            source_message_id=source_message_id,
        )
        self.db.add(card)
        self.db.flush()
        return card

    def get_owned_card(
        self,
        *,
        evidence_card_id: int,
        user_id: int,
        for_update: bool = False,
    ) -> EvidenceCard | None:
        statement = (
            select(EvidenceCard)
            .join(
                ResearchAnalysis,
                ResearchAnalysis.id == EvidenceCard.research_analysis_id,
            )
            .join(CourseProject, CourseProject.id == ResearchAnalysis.project_id)
            .where(
                EvidenceCard.id == evidence_card_id,
                CourseProject.user_id == user_id,
                CourseProject.is_deleted.is_(False),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def confirm(self, card: EvidenceCard, *, teacher_id: int) -> None:
        if card.card_status == "CONFIRMED":
            return
        card.card_status = "CONFIRMED"
        card.confirmed_by = teacher_id
        card.confirmed_at = func.now()
        self.db.flush()
