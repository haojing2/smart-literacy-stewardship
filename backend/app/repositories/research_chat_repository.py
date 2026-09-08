from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.research import (
    ResearchAnalysis,
    ResearchChatMessage,
    ResearchChatSession,
    ResearchResource,
)
from app.models.evidence_card import EvidenceCard


class ResearchChatRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_owned_project_resource(
        self, *, project_id: int, resource_id: int, user_id: int
    ) -> ResearchResource | None:
        statement = (
            select(ResearchResource)
            .join(CourseProject, CourseProject.id == ResearchResource.project_id)
            .where(
                ResearchResource.id == resource_id,
                ResearchResource.project_id == project_id,
                ResearchResource.user_id == user_id,
                CourseProject.user_id == user_id,
                CourseProject.is_deleted.is_(False),
            )
        )
        return self.db.scalar(statement)

    def get_owned_project(
        self, *, project_id: int, user_id: int, for_update: bool = False
    ) -> CourseProject | None:
        statement = select(CourseProject).where(
            CourseProject.id == project_id,
            CourseProject.user_id == user_id,
            CourseProject.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_project_id_for_resource(self, *, resource_id: int) -> int | None:
        return self.db.scalar(
            select(ResearchResource.project_id).where(
                ResearchResource.id == resource_id
            )
        )

    def get_resource(
        self, *, resource_id: int, for_update: bool = False
    ) -> ResearchResource | None:
        statement = select(ResearchResource).where(
            ResearchResource.id == resource_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_owned_session(
        self, *, session_id: int, user_id: int, for_update: bool = False
    ) -> ResearchChatSession | None:
        statement = (
            select(ResearchChatSession)
            .join(CourseProject, CourseProject.id == ResearchChatSession.project_id)
            .where(
                ResearchChatSession.id == session_id,
                CourseProject.user_id == user_id,
                CourseProject.is_deleted.is_(False),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_latest_owned_project_session(
        self, *, project_id: int, user_id: int
    ) -> ResearchChatSession | None:
        return self.db.scalar(
            select(ResearchChatSession)
            .join(CourseProject, CourseProject.id == ResearchChatSession.project_id)
            .where(
                ResearchChatSession.project_id == project_id,
                ResearchChatSession.user_id == user_id,
                ResearchChatSession.resource_id.is_(None),
                CourseProject.user_id == user_id,
                CourseProject.is_deleted.is_(False),
            )
            .order_by(desc(ResearchChatSession.updated_at), desc(ResearchChatSession.id))
            .limit(1)
        )

    def get_latest_owned_resource_session(
        self, *, project_id: int, user_id: int
    ) -> ResearchChatSession | None:
        return self.db.scalar(
            select(ResearchChatSession)
            .join(CourseProject, CourseProject.id == ResearchChatSession.project_id)
            .join(ResearchResource, ResearchResource.id == ResearchChatSession.resource_id)
            .where(
                ResearchChatSession.project_id == project_id,
                ResearchChatSession.user_id == user_id,
                ResearchChatSession.resource_id.is_not(None),
                CourseProject.user_id == user_id,
                CourseProject.is_deleted.is_(False),
                ResearchResource.project_id == project_id,
                ResearchResource.user_id == user_id,
            )
            .order_by(desc(ResearchChatSession.updated_at), desc(ResearchChatSession.id))
            .limit(1)
        )

    def get_latest_owned_resource_session_for_resource(
        self, *, project_id: int, resource_id: int, user_id: int
    ) -> ResearchChatSession | None:
        return self.db.scalar(
            select(ResearchChatSession)
            .join(CourseProject, CourseProject.id == ResearchChatSession.project_id)
            .join(ResearchResource, ResearchResource.id == ResearchChatSession.resource_id)
            .where(
                ResearchChatSession.project_id == project_id,
                ResearchChatSession.resource_id == resource_id,
                ResearchChatSession.user_id == user_id,
                CourseProject.user_id == user_id,
                CourseProject.is_deleted.is_(False),
                ResearchResource.project_id == project_id,
                ResearchResource.user_id == user_id,
            )
            .order_by(desc(ResearchChatSession.updated_at), desc(ResearchChatSession.id))
            .limit(1)
        )

    def create_session(
        self, *, user_id: int, project_id: int, resource_id: int | None, title: str
    ) -> ResearchChatSession:
        session = ResearchChatSession(
            user_id=user_id,
            project_id=project_id,
            resource_id=resource_id,
            title=title,
            status="ACTIVE",
        )
        self.db.add(session)
        self.db.flush()
        return session

    def bind_evidence_card(
        self, session: ResearchChatSession, *, evidence_card: EvidenceCard
    ) -> None:
        if session.evidence_card_id != evidence_card.id:
            session.evidence_card_id = evidence_card.id
            self.db.flush()

    def clear_evidence_card(self, session: ResearchChatSession) -> None:
        if session.evidence_card_id is not None:
            session.evidence_card_id = None
            self.db.flush()

    def get_latest_analysis(self, *, resource_id: int) -> ResearchAnalysis | None:
        statement = (
            select(ResearchAnalysis)
            .where(ResearchAnalysis.resource_id == resource_id)
            .order_by(desc(ResearchAnalysis.version))
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_latest_session_analysis(self, *, session_id: int) -> ResearchAnalysis | None:
        return self.db.scalar(
            select(ResearchAnalysis)
            .where(ResearchAnalysis.session_id == session_id)
            .order_by(desc(ResearchAnalysis.version))
            .limit(1)
        )

    def create_analysis(
        self,
        *,
        resource_id: int | None,
        session_id: int | None = None,
        project_id: int,
        version: int,
        structured_data: dict[str, object],
        field_sources: dict[str, str],
    ) -> ResearchAnalysis:
        analysis = ResearchAnalysis(
            resource_id=resource_id,
            session_id=session_id,
            project_id=project_id,
            version=version,
            structured_data_json=structured_data,
            field_sources_json=field_sources,
            status="VALIDATED",
            teacher_confirmed=False,
            teacher_confirmed_at=None,
        )
        self.db.add(analysis)
        self.db.flush()
        return analysis

    def confirm_analysis(self, analysis: ResearchAnalysis) -> None:
        analysis.teacher_confirmed = True
        analysis.teacher_confirmed_at = datetime.now()
        self.db.flush()

    def set_resource_processing_status(
        self, resource: ResearchResource, *, processing_status: str
    ) -> None:
        resource.processing_status = processing_status
        self.db.flush()

    def list_messages(
        self, *, session_id: int
    ) -> Sequence[ResearchChatMessage]:
        statement = (
            select(ResearchChatMessage)
            .where(ResearchChatMessage.session_id == session_id)
            .order_by(ResearchChatMessage.sequence_no)
        )
        return self.db.scalars(statement).all()

    def next_sequence_no(self, *, session_id: int) -> int:
        current = self.db.scalar(
            select(func.max(ResearchChatMessage.sequence_no)).where(
                ResearchChatMessage.session_id == session_id
            )
        )
        return int(current or 0) + 1

    def create_message(
        self,
        *,
        session_id: int,
        role: str,
        sequence_no: int,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> ResearchChatMessage:
        message = ResearchChatMessage(
            session_id=session_id,
            role=role,
            sequence_no=sequence_no,
            content=content,
            metadata_json=metadata,
        )
        self.db.add(message)
        self.db.flush()
        return message

    def touch_session(self, session: ResearchChatSession) -> None:
        session.updated_at = datetime.now()
        self.db.flush()

    def update_conversation_summary(
        self,
        session: ResearchChatSession,
        *,
        summary: str,
        through_sequence_no: int,
    ) -> None:
        session.conversation_summary = summary
        session.conversation_summary_through_sequence_no = through_sequence_no
        self.touch_session(session)
