from __future__ import annotations

from collections.abc import AsyncIterator
import logging

from sqlalchemy.orm import Session

from app.agents.research.base import ResearchAgentProvider
from app.agents.research.errors import ResearchAgentContractError, ResearchAgentError
from app.agents.research.context_builder import (
    ConversationContextBuilder,
    RECENT_MESSAGE_LIMIT,
)
from app.models.research import ResearchAnalysis, ResearchChatMessage, ResearchChatSession
from app.repositories.research_chat_repository import ResearchChatRepository
from app.schemas.evidence import EvidenceSourceMetadata
from app.schemas.research_assistant import (
    ResearchAnalysisRequest,
    ResearchAnalysisResult,
    ResearchChatMessageInput,
    ResearchChatMessageResponse,
    ResearchChatRequest,
    ResearchConversationMessage,
    ProjectKnowledgeSourceInput,
    ResearchChatSendMessageResponse,
    ResearchChatSessionCreateRequest,
    ResearchChatSessionResponse,
    ResearchConversationSummaryRequest,
)
from app.services.research_analysis_state_service import (
    ResearchAnalysisStateService,
)
from app.services.evidence_readiness_service import EvidenceReadinessService
from app.services.evidence_card_draft_service import EvidenceCardDraftService
from app.services.embedding_service import EmbeddingError
from app.services.bm25_store_service import BM25StoreError
from app.services.hybrid_retrieval_service import HybridRetrievalError
from app.services.project_knowledge_service import (
    ProjectKnowledgeService,
    ProjectKnowledgeSource,
)
from app.services.vector_store_service import VectorStoreError
from app.core.config import settings


logger = logging.getLogger(__name__)
# Keep ordinary short conversations verbatim.  A rolling summary starts only
# once there are more than twenty meaningful user/assistant turns.
SUMMARY_TRIGGER_MESSAGE_COUNT = 20
RESEARCH_ANALYSIS_QUERIES = (
    "participants sample learners students research subjects population",
    "research purpose research question topic objective",
    "intervention teaching strategy procedure duration treatment implementation",
    "assessment measure instrument questionnaire test scale rubric",
    "results findings significant effect learning outcome",
    "limitations implications discussion teaching implications",
)


class ResearchChatNotFoundError(LookupError):
    pass


class ResearchTextNotReadyError(RuntimeError):
    pass


class ResearchChatInactiveError(RuntimeError):
    pass


class ResearchChatService:
    """Multi-turn chat use cases depending only on ResearchAgentProvider."""

    def __init__(
        self,
        db: Session,
        provider: ResearchAgentProvider,
        project_knowledge: ProjectKnowledgeService | None = None,
    ) -> None:
        self.db = db
        self.provider = provider
        self.repository = ResearchChatRepository(db)
        self.project_knowledge = project_knowledge or ProjectKnowledgeService(db)

    async def create_session(
        self,
        *,
        current_user_id: int,
        project_id: int,
        request: ResearchChatSessionCreateRequest,
    ) -> ResearchChatSessionResponse:
        project = self.repository.get_owned_project(
            project_id=project_id,
            user_id=current_user_id,
            # Serialize get-or-create within a project without imposing a new
            # schema-level uniqueness rule on historical resource sessions.
            for_update=request.resource_id is None,
        )
        if project is None:
            raise ResearchChatNotFoundError("Research project was not found")
        if request.resource_id is None:
            existing = self.repository.get_latest_owned_project_session(
                project_id=project_id,
                user_id=current_user_id,
            )
            if existing is not None:
                self._ensure_project_analysis(existing)
                return self.get_session(
                    current_user_id=current_user_id,
                    session_id=existing.id,
                )
            try:
                session = self.repository.create_session(
                    user_id=current_user_id,
                    project_id=project_id,
                    resource_id=None,
                    title=(request.title or f"{project.title} 的研教对话")[:255],
                )
                session_id = session.id
                analysis = ResearchAnalysisStateService.with_readiness(
                    self._empty_project_analysis(),
                    EvidenceReadinessService.source_metadata_from_knowledge_base(),
                )
                self.repository.create_analysis(
                    resource_id=None,
                    session_id=session_id,
                    project_id=project_id,
                    version=1,
                    structured_data=analysis.model_dump(mode="json", by_alias=False),
                    field_sources=ResearchAnalysisStateService.initial_mock_sources(),
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            return self.get_session(
                current_user_id=current_user_id,
                session_id=session_id,
            )

        resource = self.repository.get_owned_project_resource(
            project_id=project_id,
            resource_id=request.resource_id,
            user_id=current_user_id,
        )
        if resource is None:
            raise ResearchChatNotFoundError("Research resource was not found")
        if (
            resource.processing_status not in {"TEXT_EXTRACTED", "REVIEWED", "CARD_READY"}
            or not resource.extracted_text
        ):
            raise ResearchTextNotReadyError(
                "Research resource text must be extracted before creating a chat session"
            )

        source_metadata = EvidenceReadinessService.source_metadata_from_resource(
            resource
        )

        analysis_record = self.repository.get_latest_analysis(resource_id=resource.id)
        analysis_failed = False
        if analysis_record is None:
            analysis_stage = "evidence_retrieval"
            try:
                analysis_evidence, evidence_sources, retrieved_count = (
                    await self._prepare_analysis_evidence(
                        project_id=project_id, file_id=resource.id
                    )
                )
                logger.info(
                    "Research analysis evidence prepared project_id=%s file_id=%s "
                    "retrieved_chunks=%s chunks=%s context_chars=%s",
                    project_id, resource.id, retrieved_count,
                    len(evidence_sources), len(analysis_evidence),
                )
                analysis_stage = "contract_validation"
                provider_response = await self.provider.analyze_research(
                    ResearchAnalysisRequest(
                        resource_id=resource.id,
                        analysis_evidence=analysis_evidence,
                        project_title=project.title if project else None,
                        project_topic=project.topic if project else None,
                    )
                )
                analysis = ResearchAnalysisStateService.with_readiness(
                    provider_response.data,
                    source_metadata,
                )
                logger.info(
                    "Research paper analysis completed project_id=%s file_id=%s provider=%s",
                    project_id, resource.id, provider_response.provider,
                )
            except (
                ResearchAgentError,
                EmbeddingError,
                HybridRetrievalError,
                VectorStoreError,
                BM25StoreError,
            ) as exc:
                analysis_failed = True
                analysis = ResearchAnalysisStateService.with_readiness(
                    self._empty_project_analysis(), source_metadata
                )
                logger.warning(
                    "Research paper structured analysis unavailable project_id=%s file_id=%s "
                    "exception_type=%s stage=%s",
                    project_id, resource.id, type(exc).__name__,
                    (
                        "contract_validation"
                        if isinstance(exc, ResearchAgentContractError)
                        else analysis_stage
                    ),
                )
        else:
            analysis = self._validated_analysis(
                analysis_record,
                source_metadata,
            )

        title = (request.title or f"与 {resource.original_filename} 的研究对话")[:255]
        try:
            if analysis_record is None:
                analysis_record = self.repository.create_analysis(
                    resource_id=resource.id,
                    project_id=project_id,
                    version=1,
                    structured_data=analysis.model_dump(
                        mode="json",
                        by_alias=False,
                    ),
                    field_sources=(
                        ResearchAnalysisStateService.initial_mock_sources()
                    ),
                )
            session = self.repository.create_session(
                user_id=current_user_id,
                project_id=project_id,
                resource_id=resource.id,
                title=title,
            )
            session_id = session.id
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        # A newly saved analysis is treated as a transition from an empty,
        # incomplete state so a complete initial parse can produce its draft.
        draft = None
        if not analysis_failed:
            draft = EvidenceCardDraftService(self.db).generate_draft_if_ready_transition(
                current_user_id=current_user_id,
                session_id=session_id,
                analysis_id=analysis_record.id,
                previous_readiness_status="INCOMPLETE",
            )
        if draft is not None:
            session = self.repository.get_owned_session(
                session_id=session_id, user_id=current_user_id, for_update=True
            )
            if session is not None:
                self.repository.create_message(
                    session_id=session.id,
                    role="SYSTEM",
                    sequence_no=self.repository.next_sequence_no(session_id=session.id),
                    content="当前核心研究信息已经完整，系统已生成证据卡草稿。",
                )
                self.db.commit()
        if analysis_failed:
            logger.warning(
                "Research chat session created with incomplete analysis project_id=%s "
                "file_id=%s session_id=%s",
                project_id, resource.id, session_id,
            )
        return self.get_session(
            current_user_id=current_user_id,
            session_id=session_id,
        )

    async def _prepare_analysis_evidence(
        self, *, project_id: int, file_id: int
    ) -> tuple[str, list[ProjectKnowledgeSource], int]:
        max_chunks = settings.research_analysis_max_chunks
        max_chars = settings.research_analysis_max_context_chars
        if max_chunks <= 0 or max_chars <= 0:
            raise ValueError("Research analysis evidence limits must be positive")
        topic_results: list[list[ProjectKnowledgeSource]] = []
        for query in RESEARCH_ANALYSIS_QUERIES:
            topic_results.append(
                await self.project_knowledge.search_resource(
                    project_id=project_id, file_id=file_id, query=query, top_k=5
                )
            )
        retrieved_count = sum(len(items) for items in topic_results)
        unique: dict[str, ProjectKnowledgeSource] = {}
        for rank in range(5):
            ranked = [items[rank] for items in topic_results if rank < len(items)]
            for source in sorted(ranked, key=lambda item: item.score, reverse=True):
                unique.setdefault(source.chunk_id, source)
                if len(unique) >= max_chunks:
                    break
            if len(unique) >= max_chunks:
                break
        selected = list(unique.values())
        blocks: list[str] = ["[ANALYSIS EVIDENCE]"]
        used = len(blocks[0])
        included: list[ProjectKnowledgeSource] = []
        for index, source in enumerate(selected, start=1):
            block = (
                f"\n\n[Chunk {index}]\nfilename: {source.filename}\n"
                f"chunk_id: {source.chunk_id}\ncontent:\n{source.content}"
            )
            if used + len(block) > max_chars:
                remaining = max_chars - used
                if remaining > 0:
                    blocks.append(block[:remaining])
                    included.append(source)
                break
            blocks.append(block)
            used += len(block)
            included.append(source)
        return "".join(blocks), included, retrieved_count

    def get_session(
        self, *, current_user_id: int, session_id: int
    ) -> ResearchChatSessionResponse:
        session = self.repository.get_owned_session(
            session_id=session_id,
            user_id=current_user_id,
        )
        if session is None:
            raise ResearchChatNotFoundError("Research chat session was not found")
        if session.resource_id is None:
            source_metadata = EvidenceReadinessService.source_metadata_from_knowledge_base()
            analysis_record = self._ensure_project_analysis(session)
            analysis = self._validated_analysis(analysis_record, source_metadata)
            return self._session_response(session, analysis, source_metadata)
        resource = self.repository.get_resource(resource_id=session.resource_id)
        if resource is None:
            raise ResearchChatNotFoundError("Research resource was not found")
        source_metadata = EvidenceReadinessService.source_metadata_from_resource(
            resource
        )
        analysis_record = self._require_latest_analysis(session.resource_id)
        analysis = self._validated_analysis(analysis_record, source_metadata)
        self._restore_latest_analysis_card(
            current_user_id=current_user_id,
            session=session,
            analysis_record=analysis_record,
        )
        return self._session_response(session, analysis, source_metadata)

    def get_latest_project_session(
        self, *, current_user_id: int, project_id: int
    ) -> ResearchChatSessionResponse:
        session = self.repository.get_latest_owned_project_session(
            project_id=project_id, user_id=current_user_id
        )
        if session is None:
            raise ResearchChatNotFoundError("Research chat session was not found")
        return self.get_session(
            current_user_id=current_user_id, session_id=session.id
        )

    def get_latest_resource_session(
        self, *, current_user_id: int, project_id: int
    ) -> ResearchChatSessionResponse:
        session = self.repository.get_latest_owned_resource_session(
            project_id=project_id,
            user_id=current_user_id,
        )
        if session is None:
            raise ResearchChatNotFoundError("Research resource session was not found")
        return self.get_session(current_user_id=current_user_id, session_id=session.id)

    def get_latest_resource_session_for_resource(
        self, *, current_user_id: int, project_id: int, resource_id: int
    ) -> ResearchChatSessionResponse:
        session = self.repository.get_latest_owned_resource_session_for_resource(
            project_id=project_id,
            resource_id=resource_id,
            user_id=current_user_id,
        )
        if session is None:
            raise ResearchChatNotFoundError("Research resource session was not found")
        return self.get_session(current_user_id=current_user_id, session_id=session.id)

    def _restore_latest_analysis_card(
        self,
        *,
        current_user_id: int,
        session: ResearchChatSession,
        analysis_record: ResearchAnalysis,
    ) -> None:
        cards = EvidenceCardDraftService(self.db).repository
        current = (
            cards.get_owned_card(
                evidence_card_id=session.evidence_card_id,
                user_id=current_user_id,
            )
            if session.evidence_card_id is not None
            else None
        )
        if current is not None and current.research_analysis_id == analysis_record.id:
            return
        exact = cards.get_by_analysis_id(analysis_id=analysis_record.id)
        if exact is not None:
            self.repository.bind_evidence_card(session, evidence_card=exact)
        else:
            self.repository.clear_evidence_card(session)
        self.db.commit()

    async def send_message(
        self,
        *,
        current_user_id: int,
        session_id: int,
        content: str,
    ) -> ResearchChatSendMessageResponse:
        session = self.repository.get_owned_session(
            session_id=session_id,
            user_id=current_user_id,
            for_update=True,
        )
        if session is None:
            raise ResearchChatNotFoundError("Research chat session was not found")
        if session.status != "ACTIVE":
            raise ResearchChatInactiveError("Research chat session is not active")
        if session.resource_id is None:
            return await self._send_project_message(
                current_user_id=current_user_id,
                session=session,
                content=content,
            )

        resource = self.repository.get_resource(resource_id=session.resource_id)
        if resource is None:
            raise ResearchChatNotFoundError("Research resource was not found")
        source_metadata = EvidenceReadinessService.source_metadata_from_resource(
            resource
        )
        analysis_record = self._require_latest_analysis(session.resource_id)
        analysis = self._validated_analysis(analysis_record, source_metadata)
        user_message = self.repository.create_message(
            session_id=session.id,
            role="USER",
            sequence_no=self.repository.next_sequence_no(session_id=session.id),
            content=content,
            metadata=self._message_metadata(session, delivery_status="PENDING"),
        )
        self.repository.touch_session(session)
        try:
            self.db.commit()
            self.db.refresh(user_message)
        except Exception:
            self.db.rollback()
            raise

        try:
            chat_request = await self._chat_request(
                current_user_id=current_user_id,
                session=session,
                content=content,
                analysis=analysis,
            )
            provider_response = await self.provider.chat(chat_request)
        except Exception as exc:
            self._record_user_message_failure(user_message, session=session, error=exc)
            raise
        patch = provider_response.data.analysis_patch

        session = self.repository.get_owned_session(
            session_id=session_id,
            user_id=current_user_id,
            for_update=True,
        )
        if session is None:
            raise ResearchChatNotFoundError("Research chat session was not found")
        if session.status != "ACTIVE":
            raise ResearchChatInactiveError("Research chat session is not active")
        resource = self.repository.get_resource(
            resource_id=session.resource_id,
            for_update=True,
        )
        if resource is None:
            raise ResearchChatNotFoundError("Research resource was not found")
        source_metadata = EvidenceReadinessService.source_metadata_from_resource(
            resource
        )
        current_analysis_record = self._require_latest_analysis(resource.id)
        current_analysis = self._validated_analysis(
            current_analysis_record,
            source_metadata,
        )
        previous_readiness = ResearchAnalysisStateService.readiness(
            current_analysis, source_metadata
        )
        latest_analysis = ResearchAnalysisStateService.apply_patch(
            current_analysis,
            patch,
            source_metadata,
        )
        assistant_message = self.repository.create_message(
            session_id=session.id,
            role="ASSISTANT",
            sequence_no=self.repository.next_sequence_no(session_id=session.id),
            content=provider_response.data.message,
            metadata=self._message_metadata(session, delivery_status="COMPLETED"),
        )
        self._mark_user_message_completed(user_message, session=session)
        latest_analysis_record = current_analysis_record
        if patch is not None:
            latest_analysis_record = self.repository.create_analysis(
                resource_id=resource.id,
                project_id=resource.project_id,
                version=current_analysis_record.version + 1,
                structured_data=latest_analysis.model_dump(
                    mode="json",
                    by_alias=False,
                ),
                field_sources=ResearchAnalysisStateService.sources_after_patch(
                    current_analysis_record.field_sources_json,
                    patch,
                ),
            )
            self.repository.set_resource_processing_status(
                resource,
                processing_status="TEXT_EXTRACTED",
            )
        self.repository.touch_session(session)
        try:
            self.db.commit()
            self.db.refresh(assistant_message)
        except Exception:
            self.db.rollback()
            raise

        await self._update_conversation_summary_safely(
            current_user_id=current_user_id, session_id=session_id
        )

        draft = None
        if patch is not None:
            draft = EvidenceCardDraftService(self.db).generate_draft_if_ready_transition(
                current_user_id=current_user_id,
                session_id=session_id,
                analysis_id=latest_analysis_record.id,
                previous_readiness_status=previous_readiness.readiness_status,
            )
            if draft is not None:
                session = self.repository.get_owned_session(
                    session_id=session_id, user_id=current_user_id, for_update=True
                )
                if session is not None:
                    self.repository.create_message(
                        session_id=session.id,
                        role="SYSTEM",
                        sequence_no=self.repository.next_sequence_no(session_id=session.id),
                        content="当前核心研究信息已经完整，系统已生成证据卡草稿。",
                    )
                    self.db.commit()

        retrieval_drafts = EvidenceCardDraftService(self.db).generate_retrieval_drafts(
            analysis=latest_analysis_record,
            assistant_message_id=assistant_message.id,
            sources=chat_request.project_knowledge_sources,
            interpretations=provider_response.data.evidence_interpretations,
        )

        return ResearchChatSendMessageResponse(
            session_id=session_id,
            user_message=self._message_response(user_message),
            assistant_message=self._message_response(assistant_message),
            analysis_patch=patch,
            latest_analysis=latest_analysis,
            readiness=ResearchAnalysisStateService.readiness(
                latest_analysis,
                source_metadata,
            ),
            evidence_draft_generated=draft is not None or bool(retrieval_drafts),
            evidence_card_id=(
                draft.evidence_card_id if draft else
                (retrieval_drafts[0].id if retrieval_drafts else None)
            ),
        )

    async def stream_message(
        self,
        *,
        current_user_id: int,
        session_id: int,
        content: str,
    ) -> AsyncIterator[str]:
        """Persist the user message, stream content, then persist one full reply.

        A cancelled or failed stream never creates an assistant message, so a
        partial response cannot be mistaken for a completed conversation turn.
        """
        session = self.repository.get_owned_session(
            session_id=session_id, user_id=current_user_id, for_update=True
        )
        if session is None:
            raise ResearchChatNotFoundError("Research chat session was not found")
        if session.status != "ACTIVE":
            raise ResearchChatInactiveError("Research chat session is not active")
        if session.resource_id is None:
            async for chunk in self._stream_project_message(
                current_user_id=current_user_id,
                session=session,
                content=content,
            ):
                yield chunk
            return
        resource = self.repository.get_resource(resource_id=session.resource_id)
        if resource is None:
            raise ResearchChatNotFoundError("Research resource was not found")
        source_metadata = EvidenceReadinessService.source_metadata_from_resource(resource)
        analysis = self._validated_analysis(
            self._require_latest_analysis(resource.id), source_metadata
        )
        user_message = self.repository.create_message(
            session_id=session.id,
            role="USER",
            sequence_no=self.repository.next_sequence_no(session_id=session.id),
            content=content,
            metadata=self._message_metadata(session, delivery_status="PENDING"),
        )
        self.repository.touch_session(session)
        try:
            self.db.commit()
            self.db.refresh(user_message)
        except Exception:
            self.db.rollback()
            raise

        try:
            full_response: list[str] = []
            async for chunk in self.provider.stream_chat(
                await self._chat_request(
                    current_user_id=current_user_id,
                    session=session,
                    content=content,
                    analysis=analysis,
                )
            ):
                full_response.append(chunk)
                yield chunk

            assistant_content = "".join(full_response).strip()
            if not assistant_content:
                raise RuntimeError("Research chat stream completed without content")
        except Exception as exc:
            self._record_user_message_failure(user_message, session=session, error=exc)
            raise
        session = self.repository.get_owned_session(
            session_id=session_id, user_id=current_user_id, for_update=True
        )
        if session is None or session.status != "ACTIVE":
            raise ResearchChatInactiveError("Research chat session is not active")
        assistant_message = self.repository.create_message(
            session_id=session.id,
            role="ASSISTANT",
            sequence_no=self.repository.next_sequence_no(session_id=session.id),
            content=assistant_content,
            metadata=self._message_metadata(session, delivery_status="COMPLETED"),
        )
        self._mark_user_message_completed(user_message, session=session)
        self.repository.touch_session(session)
        try:
            self.db.commit()
            self.db.refresh(assistant_message)
        except Exception:
            self.db.rollback()
            raise
        await self._update_conversation_summary_safely(
            current_user_id=current_user_id, session_id=session.id
        )

    async def _send_project_message(
        self,
        *,
        current_user_id: int,
        session: ResearchChatSession,
        content: str,
    ) -> ResearchChatSendMessageResponse:
        """Persist a project knowledge-base turn and evolve its session analysis."""
        source_metadata = EvidenceReadinessService.source_metadata_from_knowledge_base()
        current_analysis_record = self._require_latest_session_analysis(session.id)
        current_analysis = self._validated_analysis(current_analysis_record, source_metadata)
        previous_readiness = ResearchAnalysisStateService.readiness(current_analysis, source_metadata)
        user_message = self.repository.create_message(
            session_id=session.id,
            role="USER",
            sequence_no=self.repository.next_sequence_no(session_id=session.id),
            content=content,
            metadata=self._message_metadata(session, delivery_status="PENDING"),
        )
        self.repository.touch_session(session)
        try:
            self.db.commit()
            self.db.refresh(user_message)
        except Exception:
            self.db.rollback()
            raise

        try:
            chat_request = await self._chat_request(
                current_user_id=current_user_id,
                session=session,
                content=content,
                analysis=current_analysis,
            )
            provider_response = await self.provider.chat(chat_request)
        except Exception as exc:
            self._record_user_message_failure(user_message, session=session, error=exc)
            raise
        session = self.repository.get_owned_session(
            session_id=session.id,
            user_id=current_user_id,
            for_update=True,
        )
        if session is None:
            raise ResearchChatNotFoundError("Research chat session was not found")
        if session.status != "ACTIVE":
            raise ResearchChatInactiveError("Research chat session is not active")
        assistant_message = self.repository.create_message(
            session_id=session.id,
            role="ASSISTANT",
            sequence_no=self.repository.next_sequence_no(session_id=session.id),
            content=provider_response.data.message,
            metadata=self._message_metadata(session, delivery_status="COMPLETED"),
        )
        self._mark_user_message_completed(user_message, session=session)
        self.repository.touch_session(session)
        patch = provider_response.data.analysis_patch
        latest_analysis = ResearchAnalysisStateService.apply_patch(
            current_analysis, patch, source_metadata
        )
        latest_analysis_record = current_analysis_record
        if patch is not None:
            latest_analysis_record = self.repository.create_analysis(
                resource_id=None,
                session_id=session.id,
                project_id=session.project_id,
                version=current_analysis_record.version + 1,
                structured_data=latest_analysis.model_dump(mode="json", by_alias=False),
                field_sources=ResearchAnalysisStateService.sources_after_patch(
                    current_analysis_record.field_sources_json, patch
                ),
            )
        try:
            self.db.commit()
            self.db.refresh(assistant_message)
        except Exception:
            self.db.rollback()
            raise
        await self._update_conversation_summary_safely(
            current_user_id=current_user_id, session_id=session.id
        )
        draft = EvidenceCardDraftService(self.db).generate_draft_if_ready_transition(
            current_user_id=current_user_id,
            session_id=session.id,
            analysis_id=latest_analysis_record.id,
            previous_readiness_status=previous_readiness.readiness_status,
        )
        retrieval_drafts = EvidenceCardDraftService(self.db).generate_retrieval_drafts(
            analysis=latest_analysis_record,
            assistant_message_id=assistant_message.id,
            sources=chat_request.project_knowledge_sources,
            interpretations=provider_response.data.evidence_interpretations,
        )
        return ResearchChatSendMessageResponse(
            session_id=session.id,
            user_message=self._message_response(user_message),
            assistant_message=self._message_response(assistant_message),
            analysis_patch=patch,
            latest_analysis=latest_analysis,
            readiness=ResearchAnalysisStateService.readiness(latest_analysis, source_metadata),
            evidence_draft_generated=draft is not None or bool(retrieval_drafts),
            evidence_card_id=(
                draft.evidence_card_id if draft else
                (retrieval_drafts[0].id if retrieval_drafts else None)
            ),
        )

    async def _stream_project_message(
        self,
        *,
        current_user_id: int,
        session: ResearchChatSession,
        content: str,
    ) -> AsyncIterator[str]:
        user_message = self.repository.create_message(
            session_id=session.id,
            role="USER",
            sequence_no=self.repository.next_sequence_no(session_id=session.id),
            content=content,
            metadata=self._message_metadata(session, delivery_status="PENDING"),
        )
        self.repository.touch_session(session)
        try:
            self.db.commit()
            self.db.refresh(user_message)
        except Exception:
            self.db.rollback()
            raise

        try:
            full_response: list[str] = []
            async for chunk in self.provider.stream_chat(
                await self._chat_request(
                    current_user_id=current_user_id,
                    session=session,
                    content=content,
                    analysis=None,
                )
            ):
                full_response.append(chunk)
                yield chunk

            assistant_content = "".join(full_response).strip()
            if not assistant_content:
                raise RuntimeError("Research chat stream completed without content")
        except Exception as exc:
            self._record_user_message_failure(user_message, session=session, error=exc)
            raise
        session = self.repository.get_owned_session(
            session_id=session.id,
            user_id=current_user_id,
            for_update=True,
        )
        if session is None or session.status != "ACTIVE":
            raise ResearchChatInactiveError("Research chat session is not active")
        assistant_message = self.repository.create_message(
            session_id=session.id,
            role="ASSISTANT",
            sequence_no=self.repository.next_sequence_no(session_id=session.id),
            content=assistant_content,
            metadata=self._message_metadata(session, delivery_status="COMPLETED"),
        )
        self._mark_user_message_completed(user_message, session=session)
        self.repository.touch_session(session)
        try:
            self.db.commit()
            self.db.refresh(assistant_message)
        except Exception:
            self.db.rollback()
            raise
        await self._update_conversation_summary_safely(
            current_user_id=current_user_id, session_id=session.id
        )

    async def _chat_request(
        self,
        *,
        current_user_id: int,
        session: ResearchChatSession,
        content: str,
        analysis: ResearchAnalysisResult | None,
    ) -> ResearchChatRequest:
        project = self.repository.get_owned_project(
            project_id=session.project_id,
            user_id=current_user_id,
        )
        if project is None:
            raise ResearchChatNotFoundError("Research project was not found")
        history = self._conversation_history(session.id)
        conversation_messages = ConversationContextBuilder.build(
            conversation=session,
            messages=history,
            current_question=content,
        )
        try:
            knowledge_sources = await self.project_knowledge.search(
                project_id=session.project_id,
                query=content,
                top_k=settings.knowledge_base_retrieval_top_k,
            )
        except Exception:
            # Retrieval is an evidence enhancement. A missing/corrupt index or
            # transient embedding failure must not turn ordinary chat into 500.
            logger.warning(
                "Project knowledge retrieval degraded project_id=%s session_id=%s",
                session.project_id,
                session.id,
                exc_info=True,
            )
            knowledge_sources = []
        request_history = history
        if (
            request_history
            and request_history[-1].role == "USER"
            and request_history[-1].content.strip() == content.strip()
        ):
            request_history = request_history[:-1]
        request = ResearchChatRequest(
            resource_id=session.resource_id,
            message=content,
            history=request_history[-RECENT_MESSAGE_LIMIT:],
            analysis=analysis,
            project_title=project.title,
            project_topic=project.topic,
            grade=project.grade,
            class_hours=project.class_hours,
            conversation_summary=session.conversation_summary,
            conversation_context=self._conversation_context(
                conversation_messages=conversation_messages,
                knowledge_sources=knowledge_sources,
            ),
            conversation_messages=[
                ResearchConversationMessage(**message)
                for message in conversation_messages
            ],
            project_knowledge_sources=[
                ProjectKnowledgeSourceInput(
                    content=source.content,
                    project_id=source.project_id,
                    filename=source.filename,
                    file_id=source.file_id,
                    chunk_id=source.chunk_id,
                    chunk_index=source.chunk_index,
                    score=source.score,
                )
                for source in knowledge_sources
            ],
        )
        return request

    def _conversation_history(self, session_id: int) -> list[ResearchChatMessageInput]:
        return [
            ResearchChatMessageInput(role=message.role, content=message.content)
            for message in self.repository.list_messages(session_id=session_id)
            if message.role in {"USER", "ASSISTANT"}
        ]

    @staticmethod
    def _conversation_context(
        *,
        conversation_messages: list[dict[str, str]],
        knowledge_sources: list[ProjectKnowledgeSourceInput],
    ) -> str:
        conversation_text = "\n".join(
            f"{message['role'].upper()}: {message['content']}"
            for message in conversation_messages
        )
        evidence_text = "\n\n".join(
            (
                f"Source {index} | filename={source.filename} | "
                f"file_id={source.file_id} | chunk_id={source.chunk_id} | "
                f"chunk_index={source.chunk_index}\n{source.content}"
            )
            for index, source in enumerate(knowledge_sources, start=1)
        )
        return "\n\n".join(
            (
                "[CONVERSATION HISTORY]\n" + conversation_text,
                "[PROJECT KNOWLEDGE EVIDENCE]\n"
                + (evidence_text or "No ready project knowledge sources were retrieved."),
            )
        )

    @staticmethod
    def _message_metadata(
        session: ResearchChatSession, *, delivery_status: str
    ) -> dict[str, object]:
        return {
            "conversationId": session.id,
            "projectId": session.project_id,
            "deliveryStatus": delivery_status,
        }

    def _record_user_message_failure(
        self,
        user_message: ResearchChatMessage,
        *,
        session: ResearchChatSession,
        error: Exception,
    ) -> None:
        """Keep the persisted user turn and make a failed delivery observable."""
        metadata = dict(user_message.metadata_json or {})
        metadata.update(self._message_metadata(session, delivery_status="FAILED"))
        metadata["error"] = f"{type(error).__name__}: {str(error)[:500]}"
        user_message.metadata_json = metadata
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.warning(
                "Unable to record research chat delivery failure session=%s",
                session.id,
                exc_info=True,
            )

    def _mark_user_message_completed(
        self, user_message: ResearchChatMessage, *, session: ResearchChatSession
    ) -> None:
        metadata = dict(user_message.metadata_json or {})
        metadata.update(self._message_metadata(session, delivery_status="COMPLETED"))
        metadata.pop("error", None)
        user_message.metadata_json = metadata

    async def _update_conversation_summary_safely(
        self, *, current_user_id: int, session_id: int
    ) -> None:
        try:
            await self._update_conversation_summary(
                current_user_id=current_user_id, session_id=session_id
            )
        except Exception:
            logger.warning(
                "Research conversation summary update failed for session=%s",
                session_id,
                exc_info=True,
            )

    async def _update_conversation_summary(
        self, *, current_user_id: int, session_id: int
    ) -> None:
        session = self.repository.get_owned_session(
            session_id=session_id, user_id=current_user_id
        )
        if session is None:
            return
        messages = [
            message
            for message in self.repository.list_messages(session_id=session.id)
            if message.role in {"USER", "ASSISTANT"}
        ]
        if len(messages) <= SUMMARY_TRIGGER_MESSAGE_COUNT:
            return
        older_messages = messages[:-RECENT_MESSAGE_LIMIT]
        new_summary_messages = [
            message
            for message in older_messages
            if message.sequence_no > session.conversation_summary_through_sequence_no
        ]
        if not new_summary_messages:
            return
        response = await self.provider.summarize_conversation(
            ResearchConversationSummaryRequest(
                existing_summary=session.conversation_summary,
                messages=[
                    ResearchChatMessageInput(role=message.role, content=message.content)
                    for message in new_summary_messages
                ],
            )
        )
        through_sequence_no = older_messages[-1].sequence_no
        locked_session = self.repository.get_owned_session(
            session_id=session_id, user_id=current_user_id, for_update=True
        )
        if (
            locked_session is None
            or locked_session.conversation_summary_through_sequence_no
            >= through_sequence_no
        ):
            return
        self.repository.update_conversation_summary(
            locked_session,
            summary=response.data.summary,
            through_sequence_no=through_sequence_no,
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _require_latest_analysis(self, resource_id: int) -> ResearchAnalysis:
        analysis = self.repository.get_latest_analysis(resource_id=resource_id)
        if analysis is None:
            raise ResearchChatNotFoundError("Research analysis was not found")
        return analysis

    def _require_latest_session_analysis(self, session_id: int) -> ResearchAnalysis:
        analysis = self.repository.get_latest_session_analysis(session_id=session_id)
        if analysis is None:
            raise ResearchChatNotFoundError("Project knowledge analysis was not found")
        return analysis

    def _ensure_project_analysis(self, session: ResearchChatSession) -> ResearchAnalysis:
        """Backfill the v1 analysis for project sessions created before migration 20260908_02."""
        analysis = self.repository.get_latest_session_analysis(session_id=session.id)
        if analysis is not None:
            return analysis
        source_metadata = EvidenceReadinessService.source_metadata_from_knowledge_base()
        initial = ResearchAnalysisStateService.with_readiness(
            self._empty_project_analysis(), source_metadata
        )
        try:
            analysis = self.repository.create_analysis(
                resource_id=None,
                session_id=session.id,
                project_id=session.project_id,
                version=1,
                structured_data=initial.model_dump(mode="json", by_alias=False),
                field_sources=ResearchAnalysisStateService.initial_mock_sources(),
            )
            self.db.commit()
            self.db.refresh(analysis)
            return analysis
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _empty_project_analysis() -> ResearchAnalysisResult:
        return ResearchAnalysisResult()

    @classmethod
    def _validated_analysis(
        cls,
        analysis_record: ResearchAnalysis,
        source_metadata: EvidenceSourceMetadata | None,
    ) -> ResearchAnalysisResult:
        analysis = ResearchAnalysisResult.model_validate(
            analysis_record.structured_data_json
        )
        return ResearchAnalysisStateService.with_readiness(
            analysis,
            source_metadata,
        )

    def _session_response(
        self,
        session: ResearchChatSession,
        analysis: ResearchAnalysisResult | None,
        source_metadata: EvidenceSourceMetadata | None,
    ) -> ResearchChatSessionResponse:
        messages = self.repository.list_messages(session_id=session.id)
        return ResearchChatSessionResponse(
            session_id=session.id,
            project_id=session.project_id,
            resource_id=session.resource_id,
            title=session.title,
            status=session.status,
            messages=[self._message_response(message) for message in messages],
            latest_analysis=analysis,
            readiness=(
                ResearchAnalysisStateService.readiness(analysis, source_metadata)
                if analysis is not None
                else None
            ),
            evidence_card_id=session.evidence_card_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    @staticmethod
    def _message_response(
        message: ResearchChatMessage,
    ) -> ResearchChatMessageResponse:
        return ResearchChatMessageResponse(
            message_id=message.id,
            role=message.role,
            sequence_no=message.sequence_no,
            content=message.content,
            metadata=message.metadata_json,
            created_at=message.created_at,
        )
