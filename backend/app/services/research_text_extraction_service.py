from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.research import ResearchResource
from app.repositories.research_resource_repository import ResearchResourceRepository
from app.services.document_parser_service import (
    DocumentParserService,
    DocumentParsingError,
)
from app.services.knowledge_base_path_service import KnowledgeBasePathService


class ResearchResourceNotFoundError(LookupError):
    pass


class TextExtractionInProgressError(RuntimeError):
    pass


class ResearchTextExtractionService:
    def __init__(
        self,
        db: Session,
        parser: DocumentParserService | None = None,
    ) -> None:
        self.db = db
        self.repository = ResearchResourceRepository(db)
        self.parser = parser or DocumentParserService()

    def extract_text(
        self, *, current_user_id: int, resource_id: int
    ) -> dict[str, int | str]:
        resource = self.repository.get_owned_active_resource(
            resource_id=resource_id,
            user_id=current_user_id,
        )
        if resource is None:
            raise ResearchResourceNotFoundError(
                "Research resource was not found for the current user"
            )
        if (
            resource.processing_status == "TEXT_EXTRACTED"
            and resource.extracted_text is not None
        ):
            return self._result(resource_id, resource.extracted_text)
        if resource.processing_status == "TEXT_EXTRACTING":
            raise TextExtractionInProgressError(
                "Text extraction is already in progress"
            )

        storage_key = resource.storage_key
        mime_type = resource.media_type
        self._mark_extracting(resource)

        try:
            file_path = self._resolve_file_path(storage_key)
            extracted_text = self.parser.parse(
                path=file_path,
                mime_type=mime_type,
            )
        except DocumentParsingError as exc:
            self._mark_failed(resource, str(exc))
            raise
        except OSError as exc:
            error = DocumentParsingError(
                "Unable to access the stored research file"
            )
            self._mark_failed(resource, str(error))
            raise error from exc

        try:
            self.repository.mark_text_extracted(
                resource,
                extracted_text=extracted_text,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._result(resource_id, extracted_text)

    def _mark_extracting(self, resource: ResearchResource) -> None:
        try:
            self.repository.mark_text_extracting(resource)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _mark_failed(
        self, resource: ResearchResource, error_message: str
    ) -> None:
        try:
            self.repository.mark_failed(resource, error_message=error_message)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _resolve_file_path(storage_key: str) -> Path:
        """Resolve new knowledge-base files and retain access to historical uploads."""
        key = Path(storage_key)
        knowledge_root = settings.knowledge_base_root.resolve()
        if key.parts and key.parts[0].startswith("project_"):
            file_path = (knowledge_root / key).resolve()
            if knowledge_root != file_path and knowledge_root not in file_path.parents:
                raise DocumentParsingError("Invalid knowledge-base storage path")
            return file_path
        storage_root = settings.research_storage_root.resolve()
        file_path = (storage_root / key).resolve()
        if storage_root != file_path and storage_root not in file_path.parents:
            raise DocumentParsingError("Invalid research file storage path")
        return file_path

    @staticmethod
    def _result(resource_id: int, extracted_text: str) -> dict[str, int | str]:
        return {
            "resourceId": resource_id,
            "processingStatus": "TEXT_EXTRACTED",
            "extractedText": extracted_text,
        }
