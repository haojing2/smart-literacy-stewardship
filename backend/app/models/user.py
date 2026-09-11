from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import BIGINT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course_project import CourseProject


class UserStatus(IntEnum):
    PENDING = 0
    ACTIVE = 1
    REJECTED = 2
    DISABLED = 3


class SysUser(Base):
    __tablename__ = "sys_user"
    __table_args__ = (
        UniqueConstraint("username", name="uk_username"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True
    )

    username: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )

    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False
    )

    status: Mapped[int] = mapped_column(
        TINYINT,
        nullable=False,
        default=UserStatus.ACTIVE
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    course_projects: Mapped[list[CourseProject]] = relationship(back_populates="user")
