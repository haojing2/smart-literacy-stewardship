from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.mysql import BIGINT, JSON, LONGTEXT, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResearchResource(Base):
    __tablename__ = "research_resource"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uk_research_resource_storage_key"),
        Index("idx_research_resource_owner_project", "user_id", "project_id"),
        Index("idx_research_resource_project_sha256", "project_id", "sha256"),
        Index("idx_research_resource_project_index_status", "project_id", "index_status"),
        Index(
            "idx_research_resource_project_processing_status",
            "project_id",
            "processing_status",
        ),
        CheckConstraint(
            "processing_status IN "
            "('UPLOADED', 'TEXT_EXTRACTING', 'TEXT_EXTRACTED', 'FAILED', 'REVIEWED', 'CARD_READY')",
            name="ck_research_resource_status",
        ),
        CheckConstraint(
            "index_status IN ('pending', 'parsing', 'indexing', 'ready', 'error')",
            name="ck_research_resource_index_status",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("course_project.id", name="fk_research_resource_project", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_research_resource_user", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # ``sha256`` remains the existing upload/deduplication field. ``file_hash``
    # is the local-knowledge-base metadata field and is intentionally optional
    # until a later parsing/indexing workflow populates it.
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parsed_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    index_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UPLOADED", server_default="UPLOADED"
    )
    extracted_text: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ResearchAnalysis(Base):
    __tablename__ = "research_analysis"
    __table_args__ = (
        UniqueConstraint("resource_id", "version", name="uk_research_analysis_version"),
        UniqueConstraint("session_id", "version", name="uk_research_analysis_session_version"),
        Index("idx_research_analysis_resource_status", "resource_id", "status"),
        Index("idx_research_analysis_session_status", "session_id", "status"),
        CheckConstraint("version > 0", name="ck_research_analysis_version_positive"),
        CheckConstraint("status IN ('DRAFT', 'VALIDATED')", name="ck_research_analysis_status"),
        CheckConstraint(
            "generation_status IN ('PENDING', 'READY', 'FAILED')",
            name="ck_research_analysis_generation_status",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("course_project.id", name="fk_research_analysis_project", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    resource_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("research_resource.id", name="fk_research_analysis_resource", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    session_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("research_chat_session.id", name="fk_research_analysis_session", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    structured_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    field_sources_json: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    teacher_confirmed: Mapped[bool] = mapped_column(
        Boolean(create_constraint=False),
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    teacher_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", server_default="DRAFT")
    generation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="READY", server_default="READY"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ResearchChatSession(Base):
    """The persisted research conversation, scoped to a project and user."""
    __tablename__ = "research_chat_session"
    __table_args__ = (
        Index("idx_research_chat_session_resource", "resource_id"),
        CheckConstraint("status IN ('ACTIVE', 'COMPLETED', 'ARCHIVED')", name="ck_research_chat_session_status"),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_research_chat_session_user", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("course_project.id", name="fk_research_chat_session_project", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    resource_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("research_resource.id", name="fk_research_chat_session_resource", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    evidence_card_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("evidence_card.id", name="fk_research_chat_session_evidence_card", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE", server_default="ACTIVE")
    conversation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_summary_through_sequence_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ResearchChatMessage(Base):
    """An ordered message belonging to one :class:`ResearchChatSession`."""
    __tablename__ = "research_chat_message"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_no", name="uk_research_message_sequence"),
        Index("idx_research_chat_message_session", "session_id"),
        CheckConstraint("role IN ('USER', 'SYSTEM', 'ASSISTANT')", name="ck_research_chat_message_role"),
        CheckConstraint("sequence_no > 0", name="ck_research_chat_message_sequence_positive"),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("research_chat_session.id", name="fk_research_chat_message_session", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
