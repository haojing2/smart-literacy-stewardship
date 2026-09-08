from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.research import ResearchResource


class ResearchResourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        project_id: int,
        user_id: int,
        original_filename: str,
        storage_key: str,
        media_type: str,
        size_bytes: int,
        sha256: str,
    ) -> ResearchResource:
        resource = ResearchResource(
            project_id=project_id,
            user_id=user_id,
            original_filename=original_filename,
            storage_key=storage_key,
            media_type=media_type,
            size_bytes=size_bytes,
            sha256=sha256,
            file_hash=sha256,
            index_status="pending",
            processing_status="UPLOADED",
        )
        self.db.add(resource)
        self.db.flush()
        return resource

    def get_by_project_sha256(
        self,
        *,
        project_id: int,
        sha256: str,
        for_update: bool = False,
    ) -> ResearchResource | None:
        """Find an existing project-local upload with the same content hash.

        The optional row/gap lock makes the check-and-create sequence safe for
        concurrent uploads once the composite index is present.
        """
        statement = select(ResearchResource).where(
            ResearchResource.project_id == project_id,
            ResearchResource.sha256 == sha256,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_by_id_and_project(
        self, *, resource_id: int, project_id: int
    ) -> ResearchResource | None:
        statement = (
            select(ResearchResource)
            .where(
                ResearchResource.id == resource_id,
                ResearchResource.project_id == project_id,
            )
        )
        return self.db.scalar(statement)

    def list_ready_by_project(self, *, project_id: int) -> list[ResearchResource]:
        """Return only files whose local retrieval indexes are fully usable."""
        statement = select(ResearchResource).where(
            ResearchResource.project_id == project_id,
            ResearchResource.index_status == "ready",
        )
        return list(self.db.scalars(statement))

    def get_owned_active_resource(
        self, *, resource_id: int, user_id: int
    ) -> ResearchResource | None:
        statement = (
            select(ResearchResource)
            .join(CourseProject, CourseProject.id == ResearchResource.project_id)
            .where(
                ResearchResource.id == resource_id,
                ResearchResource.user_id == user_id,
                CourseProject.user_id == user_id,
                CourseProject.is_deleted.is_(False),
            )
            .with_for_update()
        )
        return self.db.scalar(statement)

    def mark_text_extracting(self, resource: ResearchResource) -> None:
        resource.processing_status = "TEXT_EXTRACTING"
        resource.extracted_text = None
        resource.error_message = None
        self.db.flush()

    def mark_text_extracted(
        self, resource: ResearchResource, *, extracted_text: str
    ) -> None:
        resource.processing_status = "TEXT_EXTRACTED"
        resource.extracted_text = extracted_text
        resource.error_message = None
        self.db.flush()

    def mark_failed(self, resource: ResearchResource, *, error_message: str) -> None:
        resource.processing_status = "FAILED"
        resource.extracted_text = None
        resource.error_message = error_message
        self.db.flush()

    def mark_index_parsing(self, resource: ResearchResource) -> None:
        resource.index_status = "parsing"
        resource.parsed_path = None
        resource.parse_error = None
        self.db.flush()

    def mark_index_pending(
        self, resource: ResearchResource, *, parsed_path: str
    ) -> None:
        resource.index_status = "pending"
        resource.parsed_path = parsed_path
        resource.parse_error = None
        self.db.flush()

    def mark_index_indexing(
        self, resource: ResearchResource, *, parsed_path: str
    ) -> None:
        resource.index_status = "indexing"
        resource.parsed_path = parsed_path
        resource.parse_error = None
        self.db.flush()

    def mark_index_ready(self, resource: ResearchResource) -> None:
        resource.index_status = "ready"
        resource.parse_error = None
        self.db.flush()

    def mark_index_error(
        self, resource: ResearchResource, *, parse_error: str
    ) -> None:
        resource.index_status = "error"
        resource.parse_error = parse_error
        self.db.flush()
