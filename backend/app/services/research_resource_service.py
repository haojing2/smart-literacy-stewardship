from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.research import ResearchResource
from app.repositories.project_repository import ProjectRepository
from app.repositories.research_resource_repository import ResearchResourceRepository
from app.services.project_service import ProjectNotFoundError
from app.services.knowledge_base_path_service import KnowledgeBasePathService


ALLOWED_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
UPLOAD_CHUNK_SIZE = 1024 * 1024
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


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
    ) -> None:
        self.db = db
        self.project_repository = ProjectRepository(db)
        self.resource_repository = ResearchResourceRepository(db)
        self.knowledge_base_paths = KnowledgeBasePathService()

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
                temporary_path.unlink(missing_ok=True)
                temporary_created = False
                self.db.commit()
                return UploadResearchResourceResult(
                    response=self._resource_response(existing),
                    parse_resource_id=existing.id,
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
            # Text extraction is still explicit; this id marks the resource as
            # eligible for indexing once extracted_text has been persisted.
            parse_resource_id=resource.id,
        )

    def list_resources(
        self, *, current_user_id: int, project_id: int
    ) -> list[dict[str, object]]:
        project = self.project_repository.get_by_id_and_user(
            project_id=project_id,
            user_id=current_user_id,
        )
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return [
            self._resource_list_response(item)
            for item in self.resource_repository.list_owned_by_project(
                project_id=project_id,
                user_id=current_user_id,
            )
        ]

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
    def _resource_list_response(resource: ResearchResource) -> dict[str, object]:
        return {
            **ResearchResourceService._resource_response(resource),
            "errorMessage": resource.error_message or resource.parse_error,
            "createdAt": resource.created_at,
            "updatedAt": resource.updated_at,
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
