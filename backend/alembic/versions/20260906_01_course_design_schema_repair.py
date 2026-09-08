"""Repair course-design tables when schema and Alembic history diverge.

Revision ID: 20260906_01
Revises: 20260905_02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260906_01"
down_revision = "20260905_02"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> dict[str, dict]:
    return {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _is_unsigned(column: dict) -> bool:
    return bool(getattr(column["type"], "unsigned", False))


def _add_or_repair_nullable_column(
    table_name: str, column: sa.Column, expected_type: sa.types.TypeEngine
) -> None:
    existing = _columns(table_name).get(column.name)
    if existing is None:
        op.add_column(table_name, column)
        return

    if not existing["nullable"] or str(existing["type"]).lower() != str(expected_type).lower():
        op.alter_column(
            table_name,
            column.name,
            existing_type=existing["type"],
            type_=expected_type,
            nullable=True,
        )


def upgrade() -> None:
    project_columns = _columns("course_project")

    for name in ("class_size", "lesson_minutes"):
        column = project_columns.get(name)
        if column is None:
            op.add_column(
                "course_project",
                sa.Column(name, mysql.SMALLINT(unsigned=True), nullable=True),
            )
        elif not column["nullable"] or not _is_unsigned(column):
            op.alter_column(
                "course_project",
                name,
                existing_type=column["type"],
                type_=mysql.SMALLINT(unsigned=True),
                nullable=True,
            )

    _add_or_repair_nullable_column(
        "course_project",
        sa.Column("student_experience", sa.Text(), nullable=True),
        sa.Text(),
    )
    _add_or_repair_nullable_column(
        "course_project",
        sa.Column("context_diagnosis_json", mysql.JSON(), nullable=True),
        mysql.JSON(),
    )

    is_deleted = _columns("course_project").get("is_deleted")
    if is_deleted is not None:
        op.get_bind().execute(
            sa.text("UPDATE course_project SET is_deleted = 0 WHERE is_deleted IS NULL")
        )
        default = str(is_deleted.get("default") or "").strip("'()")
        if is_deleted["nullable"] or default != "0":
            op.alter_column(
                "course_project",
                "is_deleted",
                existing_type=is_deleted["type"],
                type_=mysql.TINYINT(1),
                nullable=False,
                server_default=sa.text("0"),
            )

    _add_or_repair_nullable_column(
        "project_pedagogy",
        sa.Column("custom_name", sa.String(255), nullable=True),
        sa.String(255),
    )
    _add_or_repair_nullable_column(
        "project_pedagogy",
        sa.Column("custom_description", sa.Text(), nullable=True),
        sa.Text(),
    )
    _add_or_repair_nullable_column(
        "project_pedagogy",
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.String(32),
    )

    primary_method = _columns("project_pedagogy").get("primary_method_id")
    if primary_method is not None and (
        not primary_method["nullable"] or not _is_unsigned(primary_method)
    ):
        op.alter_column(
            "project_pedagogy",
            "primary_method_id",
            existing_type=primary_method["type"],
            type_=mysql.BIGINT(unsigned=True),
            nullable=True,
        )

    _add_or_repair_nullable_column(
        "project_activity",
        sa.Column("core_task", sa.Text(), nullable=True),
        sa.Text(),
    )
    _add_or_repair_nullable_column(
        "project_activity",
        sa.Column("assessment_note", sa.Text(), nullable=True),
        sa.Text(),
    )
    _add_or_repair_nullable_column(
        "project_activity",
        sa.Column("scaffolds_json", mysql.JSON(), nullable=True),
        mysql.JSON(),
    )


def downgrade() -> None:
    # This repair is intentionally non-destructive: existing project data stays intact.
    pass
