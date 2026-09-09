"""The sole project-scoped entry point for local knowledge-base retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.research_resource_repository import ResearchResourceRepository
from app.services.hybrid_retrieval_service import (
    HybridRetrievalIndexNotFoundError,
    HybridRetrievalService,
)


@dataclass(frozen=True)
class ProjectKnowledgeSource:
    content: str
    filename: str
    file_id: int
    chunk_id: str
    chunk_index: int
    score: float
    project_id: int | None = None


class ProjectKnowledgeService:
    """Retrieve sources only from ready files belonging to one project.

    Application callers must use this facade rather than directly operating
    FAISS, BM25, chunk files, or retrieval index paths.
    """

    def __init__(
        self,
        db: Session,
        *,
        hybrid_retrieval: HybridRetrievalService | None = None,
        resource_repository: ResearchResourceRepository | None = None,
    ) -> None:
        self._resource_repository = resource_repository or ResearchResourceRepository(
            db
        )
        self._hybrid_retrieval = hybrid_retrieval or HybridRetrievalService()

    async def search(
        self, *, project_id: int, query: str, top_k: int = 5
    ) -> list[ProjectKnowledgeSource]:
        if not isinstance(project_id, int) or isinstance(project_id, bool) or project_id <= 0:
            raise ValueError("project_id must be a positive integer")
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")

        ready_file_ids = {
            resource.id
            for resource in self._resource_repository.list_ready_by_project(
                project_id=project_id
            )
        }
        if not ready_file_ids:
            return []

        try:
            retrieved = await self._hybrid_retrieval.search(
                project_id=project_id,
                query=query,
                top_k=top_k,
            )
        except HybridRetrievalIndexNotFoundError:
            # A ready DB row can exist after manual file cleanup or before a
            # legacy index has been rebuilt. This is an empty knowledge base,
            # not a server error for callers.
            return []

        return [
            ProjectKnowledgeSource(
                content=result.content,
                project_id=project_id,
                filename=result.filename,
                file_id=result.file_id,
                chunk_id=result.chunk_id,
                chunk_index=result.chunk_index,
                score=result.score,
            )
            for result in retrieved
            if result.file_id in ready_file_ids
        ][:top_k]

    async def search_resource(
        self,
        *,
        project_id: int,
        file_id: int,
        query: str,
        top_k: int = 5,
    ) -> list[ProjectKnowledgeSource]:
        """Retrieve from one ready resource before applying either ranking cutoff."""
        if not isinstance(file_id, int) or isinstance(file_id, bool) or file_id <= 0:
            raise ValueError("file_id must be a positive integer")
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        resource = self._resource_repository.get_by_id_and_project(
            resource_id=file_id, project_id=project_id
        )
        if resource is None or resource.index_status != "ready":
            return []
        try:
            retrieved = await self._hybrid_retrieval.search(
                project_id=project_id,
                query=query,
                top_k=top_k,
                allowed_file_ids={file_id},
            )
        except HybridRetrievalIndexNotFoundError:
            return []
        return [
            ProjectKnowledgeSource(
                content=result.content,
                project_id=project_id,
                filename=result.filename,
                file_id=result.file_id,
                chunk_id=result.chunk_id,
                chunk_index=result.chunk_index,
                score=result.score,
            )
            for result in retrieved
        ]
