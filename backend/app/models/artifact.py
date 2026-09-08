from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Artifact(Base):
    """A final exported file, distinct from an editable teaching resource."""

    __tablename__ = "artifact"
    __table_args__ = (
        Index("idx_artifact_project_type", "project_id", "artifact_type", "version"),
        Index("idx_artifact_resource_version", "resource_version_id"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("course_project.id", name="fk_artifact_project", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_html: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, default=1)
    resource_version_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("teaching_resource_version.id", name="fk_artifact_resource_version", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    file_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
