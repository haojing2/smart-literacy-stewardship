"""Align course_project soft-delete columns and index without physical deletion."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260827_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("course_project")}

    if "is_deleted" not in columns:
        op.add_column(
            "course_project",
            sa.Column("is_deleted", mysql.TINYINT(1), nullable=False, server_default=sa.text("0")),
        )
    else:
        bind.execute(sa.text("UPDATE course_project SET is_deleted = 0 WHERE is_deleted IS NULL"))
        is_deleted = columns["is_deleted"]
        if is_deleted["nullable"] or is_deleted.get("default") not in {"0", "b'0'", "0"}:
            op.alter_column(
                "course_project",
                "is_deleted",
                existing_type=mysql.TINYINT(1),
                nullable=False,
                server_default=sa.text("0"),
            )

    if "deleted_at" not in columns:
        op.add_column("course_project", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    index_names = {index["name"] for index in inspector.get_indexes("course_project")}
    if "idx_course_project_user_deleted" not in index_names:
        op.create_index(
            "idx_course_project_user_deleted",
            "course_project",
            ["user_id", "is_deleted"],
        )


def downgrade() -> None:
    """Intentionally non-destructive: soft-delete history must not be removed."""
    pass
