from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.research import ResearchResource
from app.db.session import SessionLocal
from app.repositories.project_repository import ProjectRepository
from app.repositories.research_resource_repository import ResearchResourceRepository
from app.services.document_parser_service import (
    DocumentParserService,
    PDF_MIME_TYPE,
)
from app.services.project_service import ProjectNotFoundError
from app.services.knowledge_base_path_service import KnowledgeBasePathService
from app.services.chunk_service import ChunkService, ChunkingError
from app.services.embedding_service import EmbeddingService
from app.services.bm25_store_service import BM25StoreService
from app.services.vector_store_service import VectorStoreService


ALLOWED_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
UPLOAD_CHUNK_SIZE = 1024 * 1024
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
logger = logging.getLogger(__name__)


class InvalidResearchFileError(ValueError):
    pass


class ResearchFileTooLargeError(ValueError):
    pass


@dataclass(frozen=True)
class UploadResearchResourceResult:
    response: dict[str, int | str]
    parse_resource_id: int | None


class ResearchResourceService:
    def __init__(
        self,
        db: Session,
        document_parser: DocumentParserService | None = None,
        chunk_service: ChunkService | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStoreService | None = None,
        bm25_store: BM25StoreService | None = None,
    ) -> None:
        self.db = db
        self.project_repository = ProjectRepository(db)
        self.resource_repository = ResearchResourceRepository(db)
        self.knowledge_base_paths = KnowledgeBasePathService()
        self.document_parser = document_parser or DocumentParserService()
        self.chunk_service = chunk_service or ChunkService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStoreService(
            self.knowledge_base_paths
        )
        self.bm25_store = bm25_store or BM25StoreService(self.knowledge_base_paths)

    async def upload(
        self,
        *,
        current_user_id: int,
        project_id: int,
        upload: UploadFile,
    ) -> UploadResearchResourceResult:
        project = self.project_repository.get_by_id_and_user(
            project_id=project_id,
            user_id=current_user_id,
        )
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")

        file_name, extension = self._safe_file_name(upload.filename)
        mime_type = ALLOWED_MEDIA_TYPES[extension]
        temporary_path = self.knowledge_base_paths.temporary_raw_file(project.id)

        digest = hashlib.sha256()
        size_bytes = 0
        temporary_created = False
        destination: Path | None = None
        try:
            with temporary_path.open("xb") as output:
                temporary_created = True
                while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                    size_bytes += len(chunk)
                    if size_bytes > MAX_UPLOAD_SIZE:
                        raise ResearchFileTooLargeError(
                            "Research files cannot exceed 50 MB"
                        )
                    digest.update(chunk)
                    output.write(chunk)

            if size_bytes == 0:
                raise InvalidResearchFileError("The uploaded file is empty")
            self._validate_file_content(temporary_path, extension)

            file_hash = digest.hexdigest()
            existing = self.resource_repository.get_by_project_sha256(
                project_id=project.id,
                sha256=file_hash,
                for_update=True,
            )
            if existing is not None:
                self.db.commit()
                return UploadResearchResourceResult(
                    response=self._resource_response(existing),
                    parse_resource_id=None,
                )

            try:
                destination = self._persist_temp_file(project.id, file_name, temporary_path)
                temporary_created = False
                resource = self.resource_repository.create(
                    project_id=project.id,
                    user_id=current_user_id,
                    original_filename=file_name,
                    storage_key=self.knowledge_base_paths.storage_key(destination),
                    media_type=mime_type,
                    size_bytes=size_bytes,
                    sha256=file_hash,
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        except Exception:
            if temporary_created:
                temporary_path.unlink(missing_ok=True)
            if destination is not None:
                destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        return UploadResearchResourceResult(
            response=self._resource_response(resource),
            # Local Markdown/chunk/embedding/indexing is intentionally disabled.
            # The configured Research Agent owns the knowledge base.
            parse_resource_id=None,
        )

    @staticmethod
    async def parse_uploaded_pdf_in_background(
        *, project_id: int, resource_id: int
    ) -> None:
        """Run blocking local parsing after the HTTP response has been sent."""
        await asyncio.to_thread(
            ResearchResourceService._parse_uploaded_pdf_in_worker,
            project_id,
            resource_id,
        )

    @staticmethod
    def _parse_uploaded_pdf_in_worker(project_id: int, resource_id: int) -> None:
        db = SessionLocal()
        try:
            service = ResearchResourceService(db)
            service._parse_pending_pdf(project_id=project_id, resource_id=resource_id)
        finally:
            db.close()

    def _parse_pending_pdf(
        self,
        *,
        project_id: int,
        resource_id: int,
    ) -> None:
        """Build a local PDF-derived vector index without involving chat."""
        resource = self.resource_repository.get_by_id_and_project(
            resource_id=resource_id,
            project_id=project_id,
        )
        if resource is None or resource.media_type != PDF_MIME_TYPE:
            self.db.rollback()
            return
        if resource.index_status != "parsing":
            self.db.rollback()
            return

        stage = "parsing"
        self._log_index_stage(project_id, resource_id, stage)
        try:
            raw_path = self.knowledge_base_paths.path_from_storage_key(
                resource.storage_key
            )
            markdown = self.document_parser.parse_pdf_to_markdown(
                project_id=project_id,
                pdf_path=raw_path,
            )
            parsed_path = self.knowledge_base_paths.parsed_markdown_file(
                project_id,
                raw_path.name,
            )
            parsed_storage_key = self.knowledge_base_paths.storage_key(parsed_path)
            self.resource_repository.mark_index_indexing(
                resource,
                parsed_path=parsed_storage_key,
            )
            self.db.commit()

            stage = "chunking"
            self._log_index_stage(project_id, resource_id, stage)
            chunks = self.chunk_service.chunk_markdown(
                markdown=markdown,
                project_id=project_id,
                file_id=resource.id,
                filename=resource.original_filename,
            )
            if not chunks:
                raise ChunkingError("Parsed Markdown produced no retrieval chunks")

            stage = "embedding"
            self._log_index_stage(project_id, resource_id, stage)
            embeddings = asyncio.run(
                self.embedding_service.embed_documents(
                    [chunk.content for chunk in chunks]
                )
            )
            stage = "indexing"
            self._log_index_stage(project_id, resource_id, stage)
            self.vector_store.create_or_update_index(
                project_id=project_id,
                chunks=chunks,
                embeddings=embeddings,
            )
            stage = "keyword_indexing"
            self._log_index_stage(project_id, resource_id, stage)
            self.bm25_store.create_or_update_index(
                project_id=project_id,
                chunks=chunks,
            )

            resource = self.resource_repository.get_by_id_and_project(
                resource_id=resource_id,
                project_id=project_id,
            )
            if resource is None:
                self.db.rollback()
                return
            self.resource_repository.mark_index_ready(resource)
            self.db.commit()
            stage = "ready"
            self._log_index_stage(project_id, resource_id, stage)
        except Exception as exc:
            self.db.rollback()
            resource = self.resource_repository.get_by_id_and_project(
                resource_id=resource_id,
                project_id=project_id,
            )
            if resource is None:
                return
            self.resource_repository.mark_index_error(resource, parse_error=str(exc))
            self.db.commit()
            logger.exception(
                "Knowledge base indexing failed project_id=%s file_id=%s stage=%s error=%s",
                project_id,
                resource_id,
                stage,
                str(exc),
            )

    @staticmethod
    def _log_index_stage(project_id: int, resource_id: int, stage: str) -> None:
        logger.info(
            "Knowledge base indexing project_id=%s file_id=%s stage=%s",
            project_id,
            resource_id,
            stage,
        )

    def _persist_temp_file(self, project_id: int, file_name: str, temporary_path: Path) -> Path:
        """Copy the verified temporary upload into a newly-created final path.

        Opening the target with ``xb`` guarantees that a concurrent upload can
        never overwrite another file with the same original filename.
        """
        while True:
            destination = self.knowledge_base_paths.next_available_raw_file(
                project_id, file_name
            )
            try:
                with (
                    temporary_path.open("rb") as source,
                    destination.open("xb") as output,
                ):
                    shutil.copyfileobj(source, output, length=UPLOAD_CHUNK_SIZE)
                temporary_path.unlink()
                return destination
            except FileExistsError:
                continue
            except Exception:
                destination.unlink(missing_ok=True)
                raise

    @staticmethod
    def _resource_response(resource: ResearchResource) -> dict[str, int | str]:
        return {
            "resourceId": resource.id,
            "fileName": resource.original_filename,
            "mimeType": resource.media_type,
            "fileSize": resource.size_bytes,
            "processingStatus": resource.processing_status,
            "indexStatus": resource.index_status,
        }

    @staticmethod
    def _safe_file_name(raw_file_name: str | None) -> tuple[str, str]:
        if not raw_file_name:
            raise InvalidResearchFileError("A file name is required")
        base_name = Path(raw_file_name.replace("\\", "/")).name.strip()
        base_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base_name).rstrip(". ")
        extension = Path(base_name).suffix.lower()
        if extension not in ALLOWED_MEDIA_TYPES:
            raise InvalidResearchFileError("Only PDF and DOCX files are supported")
        if len(base_name) > 255:
            raise InvalidResearchFileError("The file name cannot exceed 255 characters")
        if not Path(base_name).stem:
            raise InvalidResearchFileError("A valid file name is required")
        return base_name, extension

    @staticmethod
    def _validate_file_content(path: Path, extension: str) -> None:
        if extension == ".pdf":
            with path.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise InvalidResearchFileError("File content is not a valid PDF")
            return

        try:
            with ZipFile(path) as document:
                members = set(document.namelist())
                if "[Content_Types].xml" not in members or "word/document.xml" not in members:
                    raise InvalidResearchFileError("File content is not a valid DOCX")
        except BadZipFile as exc:
            raise InvalidResearchFileError("File content is not a valid DOCX") from exc
