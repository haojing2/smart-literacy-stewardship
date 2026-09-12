from __future__ import annotations

from dataclasses import dataclass
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.evidence_card import EvidenceCard
from app.models.research import ResearchAnalysis, ResearchChatSession, ResearchResource
from app.repositories.evidence_card_repository import EvidenceCardRepository
from app.repositories.research_chat_repository import ResearchChatRepository
from app.schemas.evidence_card import (
    EvidenceCardDraft,
    EvidenceCardSource,
    EvidenceCardUpdateRequest,
)
from app.schemas.research_assistant import (
    EvidenceCardInterpretation,
    ProjectKnowledgeSourceInput,
    ResearchAnalysisResult,
)
from app.services.evidence_readiness_service import EvidenceReadinessService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvidenceDraftSyncResult:
    draft: EvidenceCardDraft | None
    created: bool
    action: str


class EvidenceCardNotFoundError(LookupError):
    pass


class EvidenceAnalysisStaleError(RuntimeError):
    pass


class EvidenceCardDraftService:
    """Deterministically maps validated research data into a persisted draft."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = EvidenceCardRepository(db)

    def generate_draft(
        self,
        *,
        current_user_id: int,
        analysis_id: int,
        session_id: int | None = None,
        require_readiness: bool = True,
    ) -> EvidenceCardDraft:
        chat_repository = ResearchChatRepository(self.db)
        session = None
        if session_id is not None:
            session = chat_repository.get_owned_session(
                session_id=session_id,
                user_id=current_user_id,
                for_update=True,
            )
            if session is None:
                self.db.rollback()
                raise EvidenceCardNotFoundError("Research chat session was not found")
            if session.evidence_card_id is not None:
                card = self.repository.get_owned_card(
                    evidence_card_id=session.evidence_card_id,
                    user_id=current_user_id,
                )
                if card is not None and card.research_analysis_id == analysis_id:
                    owned_card = self.repository.get_owned_analysis(
                        analysis_id=card.research_analysis_id,
                        user_id=current_user_id,
                    )
                    if owned_card is not None:
                        self.db.commit()
                        return self._response(card, owned_card[1], owned_card[0].project_id)
                # The session may still point at a card created for an older
                # analysis version. Preserve that card, but stop presenting it
                # as evidence for the latest version.
                chat_repository.clear_evidence_card(session)

        owned = self.repository.get_owned_analysis(
            analysis_id=analysis_id,
            user_id=current_user_id,
            for_update=True,
        )
        if owned is None:
            self.db.rollback()
            raise EvidenceCardNotFoundError("Research analysis was not found")
        analysis_record, resource = owned
        if self.repository.get_latest_analysis_id(
            resource_id=resource.id if resource else None,
            session_id=analysis_record.session_id,
        ) != analysis_record.id:
            self.db.rollback()
            raise EvidenceAnalysisStaleError(
                "Only the latest research analysis can generate an Evidence Card"
            )

        existing = self.repository.get_by_analysis_id(analysis_id=analysis_id)
        if existing is not None:
            if session is not None:
                chat_repository.bind_evidence_card(session, evidence_card=existing)
            self.db.commit()
            return self._response(existing, resource, analysis_record.project_id)

        analysis = ResearchAnalysisResult.model_validate(
            analysis_record.structured_data_json
        )
        source = self._source(resource, analysis_record.project_id)
        if require_readiness:
            try:
                EvidenceReadinessService.require_ready(
                    analysis,
                    self._source_metadata(resource),
                    expected_resource_id=resource.id if resource else None,
                )
            except Exception:
                self.db.rollback()
                raise
        mapped = self.map_draft(
            analysis_record=analysis_record,
            analysis=analysis,
            resource=resource,
        )
        try:
            card = self.repository.create_draft(
                analysis=analysis_record,
                resource=resource,
                title=analysis.research_topics[0]
                if analysis.research_topics
                else (resource.original_filename if resource else "讯飞研教智联知识库"),
                topic=analysis.research_topics[0]
                if analysis.research_topics
                else None,
                research_finding=mapped.research_finding,
                applicable_audience=mapped.applicable_audience,
                recommended_strategies=mapped.recommended_strategies,
                implementation_conditions=mapped.implementation_conditions,
                teaching_implications=mapped.teaching_implications,
                limitations=mapped.limitations,
                source_metadata=source.model_dump(
                    mode="json",
                    by_alias=False,
                ),
                source_text=analysis.source_excerpt or "",
            )
            if session is not None:
                chat_repository.bind_evidence_card(session, evidence_card=card)
            self.db.commit()
            self.db.refresh(card)
        except Exception:
            self.db.rollback()
            raise
        return self._response(card, resource, analysis_record.project_id)

    def generate_draft_if_ready_transition(
        self,
        *,
        current_user_id: int,
        session_id: int,
        analysis_id: int,
        previous_readiness_status: str,
    ) -> EvidenceCardDraft | None:
        """Create and bind one draft only when this session becomes READY."""
        if previous_readiness_status != "INCOMPLETE":
            return None
        synchronized = self.ensure_current_draft(
            current_user_id=current_user_id,
            session_id=session_id,
            analysis_id=analysis_id,
        )
        return synchronized.draft if synchronized.created else None

    def ensure_current_draft(
        self,
        *,
        current_user_id: int,
        session_id: int,
        analysis_id: int,
        require_readiness: bool = True,
    ) -> EvidenceDraftSyncResult:
        """Synchronize the session's synthesized card with its latest analysis.

        Historical cards are immutable. A READY analysis reuses or creates its
        own analysis-level card; an INCOMPLETE analysis clears only the session
        binding. Retrieval chunk cards are deliberately ignored here.
        """
        chat_repository = ResearchChatRepository(self.db)
        session = chat_repository.get_owned_session(
            session_id=session_id,
            user_id=current_user_id,
            for_update=True,
        )
        if session is None:
            self.db.rollback()
            raise EvidenceCardNotFoundError("Research chat session was not found")
        owned = self.repository.get_owned_analysis(
            analysis_id=analysis_id,
            user_id=current_user_id,
        )
        if owned is None:
            self.db.rollback()
            raise EvidenceCardNotFoundError("Research analysis was not found")
        analysis, resource = owned
        if (
            (resource is not None and session.resource_id != resource.id)
            or (resource is None and analysis.session_id != session.id)
        ):
            self.db.rollback()
            raise EvidenceCardNotFoundError(
                "Research analysis does not belong to this chat session"
            )
        latest_analysis_id = self.repository.get_latest_analysis_id(
            resource_id=resource.id if resource else None,
            session_id=analysis.session_id,
        )
        if latest_analysis_id != analysis.id:
            self.db.rollback()
            raise EvidenceAnalysisStaleError(
                "Only the latest research analysis can own the current Evidence Card"
            )

        previous_card_id = session.evidence_card_id
        previous_card = (
            self.repository.get_owned_card(
                evidence_card_id=previous_card_id,
                user_id=current_user_id,
            )
            if previous_card_id is not None
            else None
        )
        readiness = EvidenceReadinessService.evaluate(
            ResearchAnalysisResult.model_validate(analysis.structured_data_json),
            self._source_metadata(resource),
            expected_resource_id=resource.id if resource else None,
        )
        if require_readiness and readiness.readiness_status != "READY":
            if session.evidence_card_id is not None:
                chat_repository.clear_evidence_card(session)
            self.db.commit()
            result = EvidenceDraftSyncResult(
                draft=None,
                created=False,
                action="CLEAR_STALE",
            )
            self._log_sync(
                session=session,
                analysis=analysis,
                previous_card=previous_card,
                current_card=None,
                action=result.action,
            )
            return result

        existing = self.repository.get_by_analysis_id(analysis_id=analysis.id)
        if existing is not None:
            action = "REUSE" if session.evidence_card_id == existing.id else "REBIND"
            chat_repository.bind_evidence_card(session, evidence_card=existing)
            self.db.commit()
            result = EvidenceDraftSyncResult(
                draft=self._response(existing, resource, analysis.project_id),
                created=False,
                action=action,
            )
            self._log_sync(
                session=session,
                analysis=analysis,
                previous_card=previous_card,
                current_card=existing,
                action=action,
            )
            return result

        draft = self.generate_draft(
            current_user_id=current_user_id,
            analysis_id=analysis.id,
            session_id=session.id,
            require_readiness=require_readiness,
        )
        current_card = self.repository.get_owned_card(
            evidence_card_id=draft.evidence_card_id,
            user_id=current_user_id,
        )
        self._log_sync(
            session=session,
            analysis=analysis,
            previous_card=previous_card,
            current_card=current_card,
            action="CREATE",
        )
        return EvidenceDraftSyncResult(
            draft=draft,
            created=True,
            action="CREATE",
        )

    @staticmethod
    def _log_sync(
        *,
        session: ResearchChatSession,
        analysis: ResearchAnalysis,
        previous_card: EvidenceCard | None,
        current_card: EvidenceCard | None,
        action: str,
    ) -> None:
        logger.info(
            "Evidence draft synchronized project_id=%s session_id=%s "
            "previous_analysis_id=%s latest_analysis_id=%s latest_analysis_version=%s "
            "previous_evidence_card_id=%s previous_evidence_analysis_id=%s "
            "current_evidence_card_id=%s current_evidence_analysis_id=%s action=%s",
            analysis.project_id,
            session.id,
            previous_card.research_analysis_id if previous_card else None,
            analysis.id,
            analysis.version,
            previous_card.id if previous_card else None,
            previous_card.research_analysis_id if previous_card else None,
            current_card.id if current_card else None,
            current_card.research_analysis_id if current_card else None,
            action,
        )

    def generate_retrieval_drafts(
        self,
        *,
        analysis: ResearchAnalysis,
        assistant_message_id: int,
        sources: list[ProjectKnowledgeSourceInput],
        interpretations: list[EvidenceCardInterpretation],
    ) -> list[EvidenceCard]:
        """Create chunk-backed DRAFT cards from trusted retrieval metadata.

        The model may only interpret a known chunk.  Filename, IDs, original
        excerpt and score are selected from ``sources`` here, never accepted
        from the model response.
        """
        sources_by_chunk = {source.chunk_id: source for source in sources}
        created: list[EvidenceCard] = []
        seen_chunks: set[str] = set()
        try:
            for interpretation in interpretations:
                source = sources_by_chunk.get(interpretation.chunk_id)
                if source is None or source.chunk_id in seen_chunks:
                    continue
                seen_chunks.add(source.chunk_id)
                if self.repository.get_by_project_source_chunk(
                    project_id=analysis.project_id,
                    source_chunk_id=source.chunk_id,
                ) is not None:
                    continue
                try:
                    # The unique key is the final guard against two parallel
                    # turns creating a card for the same project chunk.
                    with self.db.begin_nested():
                        card = self.repository.create_retrieval_draft(
                            analysis=analysis,
                            project_id=analysis.project_id,
                            source_file_id=source.file_id,
                            source_filename=source.filename,
                            source_chunk_id=source.chunk_id,
                            source_text=source.content,
                            source_retrieval_score=source.score,
                            source_message_id=assistant_message_id,
                            evidence_meaning=interpretation.evidence_meaning,
                            relation_to_question=interpretation.relation_to_question,
                            synthesis=interpretation.synthesis,
                        )
                    created.append(card)
                except IntegrityError:
                    # A competing request already persisted this same chunk.
                    # It is intentionally idempotent rather than a chat error.
                    continue
            if created:
                self.db.commit()
                for card in created:
                    self.db.refresh(card)
            return created
        except Exception:
            self.db.rollback()
            raise

    def get_draft(
        self, *, current_user_id: int, evidence_card_id: int
    ) -> EvidenceCardDraft:
        card = self.repository.get_owned_card(
            evidence_card_id=evidence_card_id, user_id=current_user_id
        )
        if card is None or card.research_analysis_id is None:
            raise EvidenceCardNotFoundError("Evidence Card was not found")
        owned = self.repository.get_owned_analysis(
            analysis_id=card.research_analysis_id, user_id=current_user_id
        )
        if owned is None:
            raise EvidenceCardNotFoundError("Evidence Card source was not found")
        return self._response(card, owned[1], owned[0].project_id)

    def update_draft(
        self, *, current_user_id: int, evidence_card_id: int, values: EvidenceCardUpdateRequest
    ) -> EvidenceCardDraft:
        card = self.repository.get_owned_card(
            evidence_card_id=evidence_card_id, user_id=current_user_id, for_update=True
        )
        if card is None or card.research_analysis_id is None:
            self.db.rollback()
            raise EvidenceCardNotFoundError("Evidence Card was not found")
        if card.card_status == "CONFIRMED":
            self.db.rollback()
            raise EvidenceAnalysisStaleError("A confirmed Evidence Card cannot be edited")
        owned = self.repository.get_owned_analysis(
            analysis_id=card.research_analysis_id, user_id=current_user_id
        )
        if owned is None:
            self.db.rollback()
            raise EvidenceCardNotFoundError("Evidence Card source was not found")
        card.main_finding = values.research_finding or None
        card.participants = values.applicable_audience or None
        card.recommended_strategies_json = values.recommended_strategies
        card.implementation_conditions_json = values.implementation_conditions
        card.teaching_implication = values.teaching_implications or None
        card.limitation = values.limitations or None
        try:
            self.db.commit()
            self.db.refresh(card)
        except Exception:
            self.db.rollback()
            raise
        return self._response(card, owned[1], owned[0].project_id)

    def confirm_draft(
        self,
        *,
        current_user_id: int,
        evidence_card_id: int,
    ) -> EvidenceCardDraft:
        card = self.repository.get_owned_card(
            evidence_card_id=evidence_card_id,
            user_id=current_user_id,
            for_update=True,
        )
        if card is None or card.research_analysis_id is None:
            self.db.rollback()
            raise EvidenceCardNotFoundError("Evidence Card was not found")
        owned = self.repository.get_owned_analysis(
            analysis_id=card.research_analysis_id,
            user_id=current_user_id,
        )
        if owned is None:
            self.db.rollback()
            raise EvidenceCardNotFoundError("Evidence Card source was not found")
        analysis_record, resource = owned
        if (
            card.card_status != "CONFIRMED"
            and self.repository.get_latest_analysis_id(
                resource_id=resource.id if resource else None,
                session_id=analysis_record.session_id,
            )
            != analysis_record.id
        ):
            self.db.rollback()
            raise EvidenceAnalysisStaleError(
                "A stale Evidence Card draft cannot be confirmed"
            )
        try:
            self.repository.confirm(card, teacher_id=current_user_id)
            if resource is not None:
                ResearchChatRepository(self.db).set_resource_processing_status(
                    resource, processing_status="CARD_READY"
                )
            self.db.commit()
            self.db.refresh(card)
        except Exception:
            self.db.rollback()
            raise
        return self._response(card, resource, analysis_record.project_id)

    @classmethod
    def map_draft(
        cls,
        *,
        analysis_record: ResearchAnalysis,
        analysis: ResearchAnalysisResult,
        resource: ResearchResource | None,
    ) -> EvidenceCardDraft:
        return EvidenceCardDraft(
            research_analysis_id=analysis_record.id,
            research_finding=cls._join(analysis.main_findings),
            applicable_audience=cls._join(analysis.research_subjects),
            recommended_strategies=list(analysis.teaching_strategies),
            implementation_conditions=(
                [analysis.intervention_duration]
                if analysis.intervention_duration
                else []
            ),
            teaching_implications=analysis.teaching_implications or "",
            limitations=cls._join(analysis.limitations),
            source=cls._source(resource, analysis_record.project_id),
            card_status="DRAFT",
        )

    @staticmethod
    def _source(resource: ResearchResource | None, project_id: int) -> EvidenceCardSource:
        if resource is None:
            return EvidenceCardSource(
                source_type="KNOWLEDGE_BASE",
                source_label="讯飞研教智联知识库",
                verification_note="知识库来源，具体文献依据待教师核查",
                citations=[],
                project_id=project_id,
            )
        return EvidenceCardSource(
            source_type="UPLOADED_RESOURCE",
            source_label=resource.original_filename,
            resource_id=resource.id,
            project_id=resource.project_id,
            original_filename=resource.original_filename,
            media_type=resource.media_type,
            size_bytes=resource.size_bytes,
            sha256=resource.sha256,
        )

    @staticmethod
    def _source_metadata(resource: ResearchResource | None):
        return (
            EvidenceReadinessService.source_metadata_from_resource(resource)
            if resource is not None
            else EvidenceReadinessService.source_metadata_from_knowledge_base()
        )

    @staticmethod
    def _join(values: list[str]) -> str:
        return "\n".join(value.strip() for value in values if value.strip())

    @classmethod
    def _response(
        cls,
        card: EvidenceCard,
        resource: ResearchResource | None,
        project_id: int,
    ) -> EvidenceCardDraft:
        source = cls._source(resource, project_id)
        if card.source_chunk_id is not None:
            # These details are persisted at retrieval time.  Do not fall back
            # to resource metadata or fabricate a locator such as a page.
            metadata = card.source_metadata_json or {}
            source = EvidenceCardSource(
                source_type="UPLOADED_RESOURCE",
                source_label=card.source_document or "项目资料",
                resource_id=card.source_file_id,
                project_id=card.project_id or project_id,
                original_filename=card.source_document,
                file_id=card.source_file_id,
                chunk_id=card.source_chunk_id,
                original_text=card.source_text,
                retrieval_score=card.source_retrieval_score,
                source_message_id=card.source_message_id,
                citations=metadata.get("citations", []),
            )
        return EvidenceCardDraft(
            evidence_card_id=card.id,
            research_analysis_id=card.research_analysis_id,
            research_finding=card.main_finding or "",
            applicable_audience=card.participants or "",
            recommended_strategies=card.recommended_strategies_json or [],
            implementation_conditions=(
                card.implementation_conditions_json or []
            ),
            teaching_implications=card.teaching_implication or "",
            limitations=card.limitation or "",
            source=source,
            card_status=card.card_status,
            confirmed_by=card.confirmed_by,
            confirmed_at=card.confirmed_at,
        )
