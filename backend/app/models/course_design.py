from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import BIGINT, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectObjective(Base):
    __tablename__ = "project_objective"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("course_project.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    standard_refs_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    literacy_refs_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    teacher_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean(create_constraint=False), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ProjectPedagogy(Base):
    __tablename__ = "project_pedagogy"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("course_project.id"), nullable=False)
    primary_method_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), nullable=True)
    secondary_method_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    suitable_for_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    risk_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    alternative_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
    teacher_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean(create_constraint=False), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    custom_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    custom_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ProjectAssessment(Base):
    __tablename__ = "project_assessment"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("course_project.id"), nullable=False)
    objective_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    task_content: Mapped[str] = mapped_column(Text, nullable=False)
    student_evidence_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    criteria_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean(create_constraint=False), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ProjectActivity(Base):
    __tablename__ = "project_activity"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("course_project.id"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    core_task: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_role: Mapped[str] = mapped_column(String(64), nullable=False)
    dominant_actor: Mapped[str] = mapped_column(String(32), nullable=False)
    assessment_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    scaffolds_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    objective_refs_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class QualityCheck(Base):
    __tablename__ = "quality_check"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("course_project.id"), nullable=False)
    check_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    issue: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CurriculumStandard(Base):
    __tablename__ = "curriculum_standard"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    standard_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    grade_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    performance: Mapped[str | None] = mapped_column(Text, nullable=True)


class AiLiteracyItem(Base):
    __tablename__ = "ai_literacy_item"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    dimension: Mapped[str] = mapped_column(String(100), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    grade_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    performance: Mapped[str | None] = mapped_column(Text, nullable=True)
    standard_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class DecisionLog(Base):
    __tablename__ = "decision_log"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("course_project.id"), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    biz_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    ai_proposal_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    teacher_action: Mapped[str] = mapped_column(String(32), nullable=False)
    teacher_revision_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class DesignEvidenceLink(Base):
    __tablename__ = "design_evidence_link"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    project_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("course_project.id"), nullable=False)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    biz_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    evidence_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("evidence_card.id"), nullable=False)
    principle: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_level: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class PedagogyMethod(Base):
    __tablename__ = "pedagogy_method"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    suitable_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    suitable_tasks: Mapped[str | None] = mapped_column(Text, nullable=True)
    typical_structure: Mapped[str | None] = mapped_column(Text, nullable=True)
    teacher_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_note: Mapped[str | None] = mapped_column(Text, nullable=True)
