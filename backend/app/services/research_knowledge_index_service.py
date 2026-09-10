"""Build project-local retrieval indexes from persisted extracted text."""

from __future__ import annotations

import asyncio
import logging
import re

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.research_resource_repository import ResearchResourceRepository
from app.services.bm25_store_service import BM25StoreService
from app.services.chunk_service import ChunkService, ChunkingError
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_base_path_service import KnowledgeBasePathService
from app.services.vector_store_service import VectorStoreService


logger = logging.getLogger(__name__)


class ResearchKnowledgeIndexService:
    """Own the extracted-text -> hybrid-index lifecycle for one resource."""

    def __init__(
        self,
        db: Session,
        *,
        chunk_service: ChunkService | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStoreService | None = None,
        bm25_store: BM25StoreService | None = None,
        paths: KnowledgeBasePathService | None = None,
    ) -> None:
        self.db = db
        self.repository = ResearchResourceRepository(db)
        self.paths = paths or KnowledgeBasePathService()
        self.chunk_service = chunk_service or ChunkService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStoreService(self.paths)
        self.bm25_store = bm25_store or BM25StoreService(self.paths)

    @staticmethod
    async def index_resource_in_background(
        *, project_id: int, resource_id: int, bind: object | None = None
    ) -> None:
        await asyncio.to_thread(
            ResearchKnowledgeIndexService._index_resource_in_worker,
            project_id,
            resource_id,
            bind,
        )

    @staticmethod
    def _index_resource_in_worker(
        project_id: int, resource_id: int, bind: object | None = None
    ) -> None:
        # Preserve the database routing selected by the request dependency.
        # Direct job-runner callers still use the application's default engine.
        db = Session(bind=bind) if bind is not None else SessionLocal()
        try:
            ResearchKnowledgeIndexService(db).index_extracted_resource(
                project_id=project_id,
                resource_id=resource_id,
            )
        finally:
            db.close()

    def index_extracted_resource(self, *, project_id: int, resource_id: int) -> None:
        resource = self.repository.get_by_id_and_project(
            resource_id=resource_id,
            project_id=project_id,
        )
        if resource is None:
            return
        if resource.index_status == "ready":
            return
        if not resource.extracted_text or resource.processing_status not in {
            "TEXT_EXTRACTED",
            "REVIEWED",
            "CARD_READY",
        }:
            return

        stage = "indexing"
        self._log(project_id, resource_id, stage)
        try:
            parsed_path = self.paths.parsed_markdown_file(
                project_id,
                self.paths.path_from_storage_key(resource.storage_key).name,
            )
            parsed_path.write_text(resource.extracted_text, encoding="utf-8")
            content_format = (
                "MARKDOWN"
                if re.search(r"(?m)^#{1,6}\\s+", resource.extracted_text)
                else "PLAIN_TEXT"
            )
            logger.info(
                "Research knowledge source format project_id=%s file_id=%s "
                "content_format=%s",
                project_id,
                resource_id,
                content_format,
            )
            self.repository.mark_index_indexing(
                resource,
                parsed_path=self.paths.storage_key(parsed_path),
            )
            self.db.commit()

            stage = "chunking"
            self._log(project_id, resource_id, stage)
            chunks = self.chunk_service.chunk_markdown(
                markdown=resource.extracted_text,
                project_id=project_id,
                file_id=resource.id,
                filename=resource.original_filename,
            )
            if not chunks:
                raise ChunkingError("Extracted text produced no retrieval chunks")

            stage = "embedding"
            self._log(project_id, resource_id, stage)
            embeddings = asyncio.run(
                self.embedding_service.embed_documents(
                    [chunk.content for chunk in chunks]
                )
            )

            stage = "faiss"
            self._log(project_id, resource_id, stage)
            self.vector_store.create_or_update_index(
                project_id=project_id,
                chunks=chunks,
                embeddings=embeddings,
            )

            stage = "bm25"
            self._log(project_id, resource_id, stage)
            self.bm25_store.create_or_update_index(
                project_id=project_id,
                chunks=chunks,
            )

            resource = self.repository.get_by_id_and_project(
                resource_id=resource_id,
                project_id=project_id,
            )
            if resource is None:
                return
            self.repository.mark_index_ready(resource)
            self.db.commit()
            logger.info(
                "Research knowledge index ready project_id=%s file_id=%s "
                "chunk_count=%s index_status=ready",
                project_id,
                resource_id,
                len(chunks),
            )
            self._log(project_id, resource_id, "ready")
        except Exception as exc:
            self.db.rollback()
            resource = self.repository.get_by_id_and_project(
                resource_id=resource_id,
                project_id=project_id,
            )
            if resource is not None:
                self.repository.mark_index_error(resource, parse_error=str(exc))
                self.db.commit()
            logger.exception(
                "Research knowledge indexing failed project_id=%s file_id=%s stage=%s error=%s",
                project_id,
                resource_id,
                stage,
                str(exc),
            )

    @staticmethod
    def _log(project_id: int, resource_id: int, stage: str) -> None:
        logger.info(
            "Research knowledge indexing project_id=%s file_id=%s stage=%s",
            project_id,
            resource_id,
            stage,
        )
