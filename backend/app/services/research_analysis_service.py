from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.research import ResearchAnalysis
from app.repositories.research_chat_repository import ResearchChatRepository
from app.schemas.evidence import EvidenceSourceMetadata
from app.schemas.research_assistant import (
    ResearchAnalysisEditRequest,
    ResearchAnalysisResult,
    ResearchAnalysisVersionResponse,
)
from app.services.evidence_readiness_service import EvidenceReadinessService
from app.services.evidence_card_draft_service import EvidenceCardDraftService
from app.services.research_analysis_state_service import (
    ResearchAnalysisStateService,
)


class ResearchAnalysisNotFoundError(LookupError):
    pass


class ResearchAnalysisNotReadyError(RuntimeError):
    pass


class EvidenceCardGenerationNotReadyError(RuntimeError):
    pass


class ResearchAnalysisService:
    """Teacher-owned analysis editing and confirmation use cases."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ResearchChatRepository(db)

    def update_analysis(
        self,
        *,
        current_user_id: int,
        session_id: int,
        request: ResearchAnalysisEditRequest,
    ) -> ResearchAnalysisVersionResponse:
        session = self.repository.get_owned_session(
            session_id=session_id,
            user_id=current_user_id,
            for_update=True,
        )
        if session is None:
            raise ResearchAnalysisNotFoundError(
                "Research chat session was not found"
            )
        resource = None
        if session.resource_id is not None:
            resource = self.repository.get_resource(resource_id=session.resource_id, for_update=True)
            if resource is None:
                raise ResearchAnalysisNotFoundError("Research resource was not found")
        source_metadata = (EvidenceReadinessService.source_metadata_from_resource(resource)
                           if resource else EvidenceReadinessService.source_metadata_from_knowledge_base())
        current = (self._require_latest_analysis(resource.id) if resource
                   else self._require_latest_session_analysis(session.id))
        current_data = self._validated_analysis(current, source_metadata)
        updated_data = ResearchAnalysisStateService.from_edit_request(
            request,
            source_excerpt=current_data.source_excerpt,
            source_metadata=source_metadata,
        )

        try:
            updated = self.repository.create_analysis(
                resource_id=resource.id if resource else None,
                session_id=session.id if resource is None else None,
                project_id=session.project_id,
                version=current.version + 1,
                structured_data=updated_data.model_dump(
                    mode="json",
                    by_alias=False,
                ),
                field_sources=ResearchAnalysisStateService.teacher_sources(),
            )
            self.repository.clear_evidence_card(session)
            # Editing invalidates a previous review until the new version is confirmed.
            if resource is not None:
                self.repository.set_resource_processing_status(resource, processing_status="TEXT_EXTRACTED")
            self.db.commit()
            self.db.refresh(updated)
        except Exception:
            self.db.rollback()
            raise
        response = self._response(
            session_id=session_id,
            analysis_record=updated,
            analysis=updated_data,
            source_metadata=source_metadata,
        )
        return response

    def generate_evidence_card(
        self, *, current_user_id: int, session_id: int
    ):
        session = self.repository.get_owned_session(
            session_id=session_id, user_id=current_user_id, for_update=True
        )
        if session is None:
            raise ResearchAnalysisNotFoundError("Research chat session was not found")
        resource = (
            self.repository.get_resource(resource_id=session.resource_id, for_update=True)
            if session.resource_id is not None else None
        )
        analysis = (
            self._require_latest_analysis(resource.id)
            if resource is not None else self._require_latest_session_analysis(session.id)
        )
        data = ResearchAnalysisResult.model_validate(analysis.structured_data_json)
        recognized_count = sum((bool(value) if isinstance(value, list) else bool((value or "").strip())) for value in (
            data.research_topics, data.participants, data.ai_literacy_dimensions,
            data.teaching_strategies, data.intervention, data.assessment_tools,
            data.main_findings, data.limitations, data.teaching_implications,
        ))
        if recognized_count < 6:
            raise EvidenceCardGenerationNotReadyError(
                "至少完成6项研究解析后才能生成证据卡。"
            )
        return EvidenceCardDraftService(self.db).generate_current_draft(
            current_user_id=current_user_id,
            session_id=session_id,
            analysis_id=analysis.id,
        ).draft

    def confirm_analysis(
        self,
        *,
        current_user_id: int,
        session_id: int,
    ) -> ResearchAnalysisVersionResponse:
        session = self.repository.get_owned_session(
            session_id=session_id,
            user_id=current_user_id,
            for_update=True,
        )
        if session is None:
            raise ResearchAnalysisNotFoundError(
                "Research chat session was not found"
            )
        resource = None
        if session.resource_id is not None:
            resource = self.repository.get_resource(resource_id=session.resource_id, for_update=True)
            if resource is None:
                raise ResearchAnalysisNotFoundError("Research resource was not found")
        source_metadata = (EvidenceReadinessService.source_metadata_from_resource(resource)
                           if resource else EvidenceReadinessService.source_metadata_from_knowledge_base())
        analysis_record = (self._require_latest_analysis(resource.id) if resource
                           else self._require_latest_session_analysis(session.id))
        analysis = self._validated_analysis(analysis_record, source_metadata)
        readiness = ResearchAnalysisStateService.readiness(
            analysis,
            source_metadata,
        )
        if readiness.readiness_status != "READY":
            raise ResearchAnalysisNotReadyError(
                "Research analysis is incomplete: "
                + ", ".join(readiness.missing_required_fields)
            )

        try:
            if not analysis_record.teacher_confirmed:
                self.repository.confirm_analysis(analysis_record)
            analysis_record.field_sources_json = ResearchAnalysisStateService.confirmed_sources(
                analysis_record.field_sources_json, analysis
            )
            if resource is not None:
                self.repository.set_resource_processing_status(resource, processing_status="REVIEWED")
            self.db.commit()
            self.db.refresh(analysis_record)
        except Exception:
            self.db.rollback()
            raise
        return self._response(
            session_id=session_id,
            analysis_record=analysis_record,
            analysis=analysis,
            source_metadata=source_metadata,
        )

    def _require_latest_analysis(self, resource_id: int) -> ResearchAnalysis:
        analysis = self.repository.get_latest_analysis(resource_id=resource_id)
        if analysis is None:
            raise ResearchAnalysisNotFoundError("Research analysis was not found")
        return analysis

    def _require_latest_session_analysis(self, session_id: int) -> ResearchAnalysis:
        analysis = self.repository.get_latest_session_analysis(session_id=session_id)
        if analysis is None:
            raise ResearchAnalysisNotFoundError("Research analysis was not found")
        return analysis

    @staticmethod
    def _validated_analysis(
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

    @staticmethod
    def _response(
        *,
        session_id: int,
        analysis_record: ResearchAnalysis,
        analysis: ResearchAnalysisResult,
        source_metadata: EvidenceSourceMetadata | None,
    ) -> ResearchAnalysisVersionResponse:
        field_sources = {
            **ResearchAnalysisStateService.initial_mock_sources(),
            **(analysis_record.field_sources_json or {}),
        }
        return ResearchAnalysisVersionResponse(
            session_id=session_id,
            analysis_id=analysis_record.id,
            version=analysis_record.version,
            generation_status=analysis_record.generation_status,
            latest_analysis=ResearchAnalysisStateService.editable_view(analysis),
            field_sources=field_sources,
            teacher_confirmed=analysis_record.teacher_confirmed,
            teacher_confirmed_at=analysis_record.teacher_confirmed_at,
            readiness=ResearchAnalysisStateService.readiness(
                analysis,
                source_metadata,
            ),
        )
