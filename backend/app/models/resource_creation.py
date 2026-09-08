from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, JSON, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResourceCreationJob(Base):
    __tablename__ = "resource_creation_job"
    __table_args__ = (
        Index("idx_resource_creation_job_project", "project_id"),
        Index("idx_resource_creation_job_user", "user_id"),
        Index("idx_resource_creation_job_project_status", "project_id", "status"),
        CheckConstraint(
            "mode IN ('COURSE_GENERATE', 'RESOURCE_ADAPT')",
            name="ck_resource_creation_job_mode",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("course_project.id", name="fk_resource_creation_job_project", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_resource_creation_job_user", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="COURSE_GENERATE", server_default=text("'COURSE_GENERATE'"))
    current_step: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, default=1, server_default=text("1"))
    selected_types_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    common_settings_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    resource_settings_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", server_default=text("'DRAFT'"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class TeachingResource(Base):
    __tablename__ = "teaching_resource"
    __table_args__ = (
        UniqueConstraint("job_id", "resource_type", name="uk_teaching_resource_job_type"),
        Index("idx_teaching_resource_project", "project_id"),
        Index("idx_teaching_resource_job", "job_id"),
        Index("idx_teaching_resource_project_type", "project_id", "resource_type"),
        CheckConstraint(
            "resource_type IN ('PPT', 'TEACHER_GUIDE', 'WORKSHEET', 'TASK_CARD', "
            "'AI_CASE', 'DISCUSSION', 'ASSESSMENT', 'REFLECTION')",
            name="ck_teaching_resource_type",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("resource_creation_job.id", name="fk_teaching_resource_job", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("course_project.id", name="fk_teaching_resource_project", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    settings_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="READY", server_default=text("'READY'"))
    current_version_no: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, default=1, server_default=text("1"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class TeachingResourceVersion(Base):
    __tablename__ = "teaching_resource_version"
    __table_args__ = (
        UniqueConstraint("resource_id", "version_no", name="uk_teaching_resource_version"),
        Index("idx_teaching_resource_version_resource", "resource_id"),
        Index("idx_teaching_resource_version_resource_no", "resource_id", "version_no"),
        CheckConstraint(
            "change_source IN ('AI', 'TEACHER', 'AI_ACCEPTED')",
            name="ck_teaching_resource_version_source",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("teaching_resource.id", name="fk_teaching_resource_version_resource", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    content_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    content_html: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    change_source: Mapped[str] = mapped_column(String(32), nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_teaching_resource_version_created_by", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ResourceAiSuggestion(Base):
    __tablename__ = "resource_ai_suggestion"
    __table_args__ = (
        Index("idx_resource_ai_suggestion_resource", "resource_id"),
        Index("idx_resource_ai_suggestion_base_version", "base_version_id"),
        Index("idx_resource_ai_suggestion_resource_status", "resource_id", "status"),
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REVISED', 'REJECTED')",
            name="ck_resource_ai_suggestion_status",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("teaching_resource.id", name="fk_resource_ai_suggestion_resource", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    base_version_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("teaching_resource_version.id", name="fk_resource_ai_suggestion_version", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    target_block_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suggestion_type: Mapped[str] = mapped_column(String(64), nullable=False)
    issue: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_content: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", server_default=text("'PENDING'"))
    teacher_revision: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
