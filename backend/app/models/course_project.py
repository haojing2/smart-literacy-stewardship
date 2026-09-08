from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.mysql import BIGINT, JSON, SMALLINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import SysUser


class CourseProject(Base):
    """ORM mapping for the existing ``course_project`` table.

    This model deliberately contains no table-creation or migration logic.
    """

    __tablename__ = "course_project"
    __table_args__ = (
        Index("idx_course_project_user_id", "user_id"),
        Index("idx_course_project_user_deleted", "user_id", "is_deleted"),
        Index("idx_course_project_workflow_state", "workflow_state"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "sys_user.id",
            name="fk_course_project_user",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str] = mapped_column(String(32), nullable=False)
    grade: Mapped[int | None] = mapped_column(TINYINT(unsigned=True), nullable=True)
    class_hours: Mapped[int | None] = mapped_column(TINYINT(unsigned=True), nullable=True)
    student_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_access_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    devices_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    constraints_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    additional_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_size: Mapped[int | None] = mapped_column(
        SMALLINT(unsigned=True), nullable=True
    )
    lesson_minutes: Mapped[int | None] = mapped_column(
        SMALLINT(unsigned=True), nullable=True
    )
    context_diagnosis_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    workflow_state: Mapped[str] = mapped_column(
        String(64), nullable=False, default="DRAFT", server_default="DRAFT"
    )
    stale_sections_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean(create_constraint=False), nullable=False, default=False, server_default=text("0")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        server_onupdate=func.now(),
    )

    user: Mapped[SysUser] = relationship(back_populates="course_projects")
