from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import BIGINT, JSON, LONGTEXT, SMALLINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvidenceCard(Base):
    """ORM mapping for the existing evidence_card table."""

    __tablename__ = "evidence_card"
    __table_args__ = (
        Index("idx_evidence_stage", "education_stage"),
        Index("idx_evidence_card_status_strength", "card_status", "evidence_strength"),
        Index("idx_evidence_year", "year"),
        Index("idx_evidence_embedding_key", "embedding_key"),
        Index("idx_evidence_research_analysis", "research_analysis_id"),
        Index("idx_evidence_source_message", "source_message_id"),
        UniqueConstraint("project_id", "source_chunk_id", name="uk_evidence_project_source_chunk"),
        CheckConstraint(
            "card_status IN ('DRAFT', 'CONFIRMED')",
            name="ck_evidence_card_status",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[str | None] = mapped_column(String(500), nullable=True)
    year: Mapped[int | None] = mapped_column(SMALLINT(unsigned=True), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    education_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    participants: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_design: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sample_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    main_finding: Mapped[str | None] = mapped_column(Text, nullable=True)
    effect_direction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    boundary_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_strength: Mapped[str | None] = mapped_column(String(32), nullable=True)
    teaching_implication: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_strategies_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    implementation_conditions_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_document: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Retrieval provenance is persisted separately from model-generated
    # interpretation.  These values are copied only from ProjectKnowledgeService.
    project_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("course_project.id", name="fk_evidence_card_project", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    source_file_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("research_resource.id", name="fk_evidence_card_source_file", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    source_chunk_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_message_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("research_chat_message.id", name="fk_evidence_card_source_message", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    source_page: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_text: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    source_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    search_text: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    embedding_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    card_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", server_default="DRAFT")
    research_analysis_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("research_analysis.id", name="fk_evidence_research_analysis", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    confirmed_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_evidence_confirmed_by", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
