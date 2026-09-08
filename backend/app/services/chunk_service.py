"""Local Markdown chunking for future retrieval indexing.

This module only builds in-memory chunk records. It deliberately has no
database, vector-store, LLM, or Spark dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from app.core.config import settings


class ChunkingError(ValueError):
    """Raised when Markdown cannot be converted into retrieval chunks."""


class TextSplitter(Protocol):
    def split_text(self, text: str) -> list[str]: ...


@dataclass(frozen=True)
class MarkdownChunk:
    chunk_id: str
    project_id: int
    file_id: int
    filename: str
    content: str
    chunk_index: int


class ChunkService:
    """Split Markdown with LlamaIndex while preserving project-file metadata."""

    def __init__(
        self,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        splitter: TextSplitter | None = None,
    ) -> None:
        self.chunk_size = (
            settings.knowledge_base_chunk_size
            if chunk_size is None
            else chunk_size
        )
        self.chunk_overlap = (
            settings.knowledge_base_chunk_overlap
            if chunk_overlap is None
            else chunk_overlap
        )
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")
        self._splitter = splitter or self._build_sentence_splitter()

    def chunk_markdown(
        self,
        *,
        markdown: str,
        project_id: int,
        file_id: int,
        filename: str,
    ) -> list[MarkdownChunk]:
        """Return ordered, in-memory chunks for one parsed project file."""
        if not isinstance(markdown, str) or not markdown.strip():
            raise ChunkingError("Markdown content is required for chunking")
        if not isinstance(project_id, int) or project_id <= 0:
            raise ChunkingError("project_id must be a positive integer")
        if not isinstance(file_id, int) or file_id <= 0:
            raise ChunkingError("file_id must be a positive integer")
        if not isinstance(filename, str) or not filename.strip():
            raise ChunkingError("filename is required for chunking")

        try:
            contents = self._splitter.split_text(markdown)
        except Exception as exc:
            raise ChunkingError("Unable to split Markdown into retrieval chunks") from exc

        return [
            MarkdownChunk(
                chunk_id=self._chunk_id(
                    project_id=project_id,
                    file_id=file_id,
                    chunk_index=index,
                    content=content,
                ),
                project_id=project_id,
                file_id=file_id,
                filename=filename,
                content=content,
                chunk_index=index,
            )
            for index, content in enumerate(contents)
            if content.strip()
        ]

    def _build_sentence_splitter(self) -> TextSplitter:
        try:
            from llama_index.core.node_parser import SentenceSplitter
        except ImportError as exc:
            raise ChunkingError(
                "llama-index-core is required for Markdown chunking"
            ) from exc
        return SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    @staticmethod
    def _chunk_id(
        *, project_id: int, file_id: int, chunk_index: int, content: str
    ) -> str:
        payload = f"{project_id}:{file_id}:{chunk_index}:{content}".encode("utf-8")
        return sha256(payload).hexdigest()
