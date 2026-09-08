from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.chunk_service import ChunkService
from app.services.knowledge_base_path_service import KnowledgeBasePathService
from app.services.research_resource_service import ResearchResourceService
from app.services.vector_store_service import VectorStoreService


class StubDatabase:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class StubResourceRepository:
    def __init__(self, resource: SimpleNamespace) -> None:
        self.resource = resource

    def get_by_id_and_project(
        self, *, resource_id: int, project_id: int
    ) -> SimpleNamespace | None:
        if self.resource.id == resource_id and self.resource.project_id == project_id:
            return self.resource
        return None

    @staticmethod
    def mark_index_indexing(resource: SimpleNamespace, *, parsed_path: str) -> None:
        resource.index_status = "indexing"
        resource.parsed_path = parsed_path
        resource.parse_error = None

    @staticmethod
    def mark_index_ready(resource: SimpleNamespace) -> None:
        resource.index_status = "ready"
        resource.parse_error = None

    @staticmethod
    def mark_index_error(resource: SimpleNamespace, *, parse_error: str) -> None:
        resource.index_status = "error"
        resource.parse_error = parse_error


class StubParser:
    def parse_pdf_to_markdown(self, *, project_id: int, pdf_path: Path) -> str:
        return "# Research evidence\n\nCollaborative learning improves reflection."


class StubEmbeddingService:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FailingEmbeddingService:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding endpoint unavailable")


def _build_indexing_service(
    tmp_path: Path, *, embedding_service: object
) -> tuple[ResearchResourceService, SimpleNamespace, StubDatabase, KnowledgeBasePathService]:
    paths = KnowledgeBasePathService(tmp_path / "knowledge_bases")
    raw_path = paths.raw_file(23, "paper.pdf")
    raw_path.write_bytes(b"%PDF-1.4\n%%EOF")
    resource = SimpleNamespace(
        id=7,
        project_id=23,
        media_type="application/pdf",
        storage_key=paths.storage_key(raw_path),
        original_filename="paper.pdf",
        index_status="parsing",
        parsed_path=None,
        parse_error=None,
    )
    db = StubDatabase()
    service = ResearchResourceService(
        db,  # type: ignore[arg-type]
        document_parser=StubParser(),  # type: ignore[arg-type]
        chunk_service=ChunkService(chunk_size=1000, chunk_overlap=120),
        embedding_service=embedding_service,  # type: ignore[arg-type]
        vector_store=VectorStoreService(paths),
    )
    service.knowledge_base_paths = paths
    service.resource_repository = StubResourceRepository(resource)  # type: ignore[assignment]
    return service, resource, db, paths


def test_pdf_indexing_pipeline_marks_resource_ready_and_persists_faiss(tmp_path: Path) -> None:
    service, resource, db, paths = _build_indexing_service(
        tmp_path, embedding_service=StubEmbeddingService()
    )

    service._parse_pending_pdf(project_id=23, resource_id=7)

    assert resource.index_status == "ready"
    assert resource.parsed_path == "project_23/parsed/paper.md"
    assert db.commits == 2
    assert VectorStoreService(paths).load_index(23).chunks[0].file_id == 7


def test_pdf_indexing_pipeline_marks_resource_error_when_embedding_fails(
    tmp_path: Path,
) -> None:
    service, resource, _, _ = _build_indexing_service(
        tmp_path, embedding_service=FailingEmbeddingService()
    )

    service._parse_pending_pdf(project_id=23, resource_id=7)

    assert resource.index_status == "error"
    assert resource.parse_error == "embedding endpoint unavailable"
