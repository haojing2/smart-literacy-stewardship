"""Add minimal course-design persistence fields and align workflow states.

Revision ID: 20260905_01
Revises: 20260903_05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260905_01"
down_revision = "20260903_05"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    # All additions are nullable so legacy project rows and research data remain valid.
    project_columns = {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns("course_project")
    }
    # The live legacy database predates its soft-delete migration. Make the
    # existing ORM contract true before this revision is stamped as its base.
    if project_columns["is_deleted"]["nullable"]:
        bind = op.get_bind()
        bind.execute(
            sa.text("UPDATE course_project SET is_deleted = 0 WHERE is_deleted IS NULL")
        )
        op.alter_column(
            "course_project",
            "is_deleted",
            existing_type=mysql.TINYINT(1),
            nullable=False,
            server_default=sa.text("0"),
        )

    _add_column_if_missing(
        "course_project", sa.Column("student_experience", sa.Text(), nullable=True)
    )
    _add_column_if_missing(
        "course_project", sa.Column("class_size", mysql.SMALLINT(unsigned=True), nullable=True)
    )
    _add_column_if_missing(
        "course_project", sa.Column("lesson_minutes", mysql.SMALLINT(unsigned=True), nullable=True)
    )
    _add_column_if_missing(
        "course_project", sa.Column("context_diagnosis_json", mysql.JSON(), nullable=True)
    )

    _add_column_if_missing(
        "project_pedagogy", sa.Column("custom_name", sa.String(255), nullable=True)
    )
    _add_column_if_missing(
        "project_pedagogy", sa.Column("custom_description", sa.Text(), nullable=True)
    )
    _add_column_if_missing(
        "project_pedagogy", sa.Column("source_type", sa.String(32), nullable=True)
    )

    _add_column_if_missing(
        "project_activity", sa.Column("core_task", sa.Text(), nullable=True)
    )
    _add_column_if_missing(
        "project_activity", sa.Column("assessment_note", sa.Text(), nullable=True)
    )
    _add_column_if_missing(
        "project_activity", sa.Column("scaffolds_json", mysql.JSON(), nullable=True)
    )

    # Preserve existing rows while moving old code states to their equivalent
    # confirmed states. No table, key, relationship, or legacy column is removed.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE course_project SET workflow_state = CASE workflow_state "
            "WHEN 'OBJECTIVE_READY' THEN 'OBJECTIVE_CONFIRMED' "
            "WHEN 'PEDAGOGY_READY' THEN 'PEDAGOGY_CONFIRMED' "
            "WHEN 'ASSESSMENT_READY' THEN 'ASSESSMENT_CONFIRMED' "
            "ELSE workflow_state END"
        )
    )


def downgrade() -> None:
    # Retain data-bearing fields on downgrade; historical project records must
    # never be destructively rewritten. Only restore legacy workflow labels.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE course_project SET workflow_state = CASE workflow_state "
            "WHEN 'OBJECTIVE_CONFIRMED' THEN 'OBJECTIVE_READY' "
            "WHEN 'PEDAGOGY_CONFIRMED' THEN 'PEDAGOGY_READY' "
            "WHEN 'ASSESSMENT_CONFIRMED' THEN 'ASSESSMENT_READY' "
            "ELSE workflow_state END"
        )
    )
