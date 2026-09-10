from __future__ import annotations

from app.models.research import ResearchResource
from app.schemas.evidence import EvidenceReadinessResult, EvidenceSourceMetadata
from app.schemas.research_assistant import ResearchAnalysisResult


class EvidenceNotReadyError(RuntimeError):
    def __init__(self, readiness: EvidenceReadinessResult) -> None:
        self.readiness = readiness
        super().__init__(
            "Evidence Card requirements are incomplete: "
            + ", ".join(readiness.missing_required_fields)
        )


class EvidenceReadinessService:
    """Backend-only policy for determining Evidence Card generation readiness."""

    REQUIRED_WEIGHTS = {
        "mainFindings": 15,
        "sourceMetadata": 15,
        "researchContext": 10,
    }
    RECOMMENDED_WEIGHTS = {
        "participants": 8,
        "researchTopic": 8,
        "aiLiteracyDimensions": 8,
        "teachingStrategies": 10,
        "intervention": 8,
        "assessmentTools": 10,
        "limitations": 8,
    }

    @classmethod
    def evaluate(
        cls,
        analysis: ResearchAnalysisResult,
        source_metadata: EvidenceSourceMetadata | None,
        *,
        expected_resource_id: int | None = None,
    ) -> EvidenceReadinessResult:
        required = {
            "mainFindings": cls._has_list_value(analysis.main_findings),
            "sourceMetadata": cls._has_source_metadata(
                source_metadata,
                expected_resource_id=expected_resource_id,
            ),
            "researchContext": (
                cls._has_list_value(analysis.research_subjects)
                or cls._has_list_value(analysis.research_topics)
            ),
        }
        recommended = {
            "participants": cls._has_list_value(analysis.research_subjects),
            "researchTopic": cls._has_list_value(analysis.research_topics),
            "aiLiteracyDimensions": cls._has_list_value(
                analysis.ai_literacy_dimensions
            ),
            "teachingStrategies": cls._has_list_value(
                analysis.teaching_strategies
            ),
            "intervention": cls._has_text(analysis.intervention_duration),
            "assessmentTools": cls._has_list_value(analysis.assessment_tools),
            "limitations": cls._has_list_value(analysis.limitations),
        }
        missing_required = [
            field for field, complete in required.items() if not complete
        ]
        missing_recommended = [
            field for field, complete in recommended.items() if not complete
        ]
        score = sum(
            cls.REQUIRED_WEIGHTS[field]
            for field, complete in required.items()
            if complete
        ) + sum(
            cls.RECOMMENDED_WEIGHTS[field]
            for field, complete in recommended.items()
            if complete
        )

        # Generation eligibility is intentionally independent of score.
        status = "READY" if not missing_required else "INCOMPLETE"
        return EvidenceReadinessResult(
            ready=status == "READY",
            readiness_score=score,
            readiness_status=status,
            missing_required_fields=missing_required,
            missing_recommended_fields=missing_recommended,
        )

    @classmethod
    def require_ready(
        cls,
        analysis: ResearchAnalysisResult,
        source_metadata: EvidenceSourceMetadata | None,
        *,
        expected_resource_id: int | None = None,
    ) -> EvidenceReadinessResult:
        readiness = cls.evaluate(
            analysis,
            source_metadata,
            expected_resource_id=expected_resource_id,
        )
        if readiness.readiness_status != "READY":
            raise EvidenceNotReadyError(readiness)
        return readiness

    @staticmethod
    def source_metadata_from_resource(
        resource: ResearchResource,
    ) -> EvidenceSourceMetadata:
        return EvidenceSourceMetadata(
            source_type="UPLOADED_RESOURCE",
            resource_id=resource.id,
            original_filename=resource.original_filename,
            media_type=resource.media_type,
            sha256=resource.sha256,
        )

    @staticmethod
    def source_metadata_from_knowledge_base() -> EvidenceSourceMetadata:
        return EvidenceSourceMetadata(source_type="KNOWLEDGE_BASE")

    @staticmethod
    def _has_list_value(values: list[str]) -> bool:
        return any(value.strip() for value in values)

    @staticmethod
    def _has_text(value: str | None) -> bool:
        return bool(value and value.strip())

    @classmethod
    def _has_source_metadata(
        cls,
        metadata: EvidenceSourceMetadata | None,
        *,
        expected_resource_id: int | None,
    ) -> bool:
        if metadata and metadata.source_type == "KNOWLEDGE_BASE":
            return expected_resource_id is None
        return bool(
            metadata
            and metadata.resource_id is not None
            and metadata.resource_id > 0
            and (
                expected_resource_id is None
                or metadata.resource_id == expected_resource_id
            )
            and cls._has_text(metadata.original_filename)
            and cls._has_text(metadata.media_type)
            and metadata.sha256 is not None
            and len(metadata.sha256) == 64
            and all(
                character in "0123456789abcdefABCDEF"
                for character in metadata.sha256
            )
        )
