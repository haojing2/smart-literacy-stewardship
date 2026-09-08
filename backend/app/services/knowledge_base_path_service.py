"""Centralized, platform-independent paths for project knowledge-base data."""

from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.core.config import settings


class KnowledgeBasePathService:
    """Owns the on-disk layout; callers never compose project paths themselves."""

    _SUBDIRECTORIES = ("raw", "parsed", "index")

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or settings.knowledge_base_root).resolve()

    def project_root(self, project_id: int) -> Path:
        """Create and return ``project_{id}`` and all required child directories."""
        if not isinstance(project_id, int) or isinstance(project_id, bool) or project_id <= 0:
            raise ValueError("project_id must be a positive integer")
        project_root = self._root / f"project_{project_id}"
        project_root.mkdir(parents=True, exist_ok=True)
        for name in self._SUBDIRECTORIES:
            (project_root / name).mkdir(exist_ok=True)
        return project_root

    def raw_dir(self, project_id: int) -> Path:
        return self.project_root(project_id) / "raw"

    def parsed_dir(self, project_id: int) -> Path:
        return self.project_root(project_id) / "parsed"

    def index_dir(self, project_id: int) -> Path:
        return self.project_root(project_id) / "index"

    def faiss_index_file(self, project_id: int) -> Path:
        return self.index_dir(project_id) / "index.faiss"

    def faiss_metadata_file(self, project_id: int) -> Path:
        return self.index_dir(project_id) / "metadata.json"

    def bm25_index_file(self, project_id: int) -> Path:
        return self.index_dir(project_id) / "bm25.json"

    def raw_file(self, project_id: int, file_name: str) -> Path:
        """Return a candidate raw-file path; callers must still create it atomically."""
        return self.raw_dir(project_id) / file_name

    def parsed_markdown_file(self, project_id: int, source_file_name: str) -> Path:
        """Return the Markdown counterpart for a raw source filename."""
        source_name = Path(source_file_name).name
        if not source_name or not Path(source_name).stem:
            raise ValueError("source_file_name must contain a file name")
        return self.parsed_dir(project_id) / f"{Path(source_name).stem}.md"

    def temporary_raw_file(self, project_id: int) -> Path:
        """Return a private temporary path in the project's raw directory."""
        return self.raw_dir(project_id) / f".upload-{uuid4().hex}.tmp"

    def next_available_raw_file(self, project_id: int, file_name: str) -> Path:
        """Preserve the original filename, suffixing only real file collisions."""
        initial = self.raw_file(project_id, file_name)
        stem, suffix = initial.stem, initial.suffix
        candidate = initial
        sequence = 1
        while candidate.exists():
            candidate = initial.with_name(f"{stem} ({sequence}){suffix}")
            sequence += 1
        return candidate

    def storage_key(self, path: Path) -> str:
        """Return a portable database key relative to the knowledge-base root."""
        resolved = path.resolve()
        if self._root != resolved and self._root not in resolved.parents:
            raise ValueError("path is outside the knowledge-base root")
        return resolved.relative_to(self._root).as_posix()

    def path_from_storage_key(self, storage_key: str) -> Path:
        """Resolve a knowledge-base storage key without allowing path traversal."""
        candidate = (self._root / PurePosixPath(storage_key)).resolve()
        if self._root != candidate and self._root not in candidate.parents:
            raise ValueError("storage key is outside the knowledge-base root")
        return candidate
