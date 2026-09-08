"""Complete the Mode A resource-creation field contract.

Revision ID: 20260906_05
Revises: 20260906_04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260906_05"
down_revision = "20260906_04"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> dict[str, dict]:
    return {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _add_missing_columns(table_name: str, columns: tuple[sa.Column, ...]) -> None:
    existing_columns = _columns(table_name)
    for column in columns:
        if column.name not in existing_columns:
            op.add_column(table_name, column)


def upgrade() -> None:
    _add_missing_columns(
        "resource_creation_job",
        (
            sa.Column("current_step", mysql.TINYINT(unsigned=True), nullable=False, server_default=sa.text("1")),
            sa.Column("resource_settings_json", mysql.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
        ),
    )
    job_columns = _columns("resource_creation_job")
    op.alter_column(
        "resource_creation_job",
        "mode",
        existing_type=job_columns["mode"]["type"],
        type_=sa.String(32),
        nullable=False,
        server_default=sa.text("'COURSE_GENERATE'"),
    )

    _add_missing_columns(
        "teaching_resource",
        (sa.Column("error_message", sa.Text(), nullable=True),),
    )
    resource_columns = _columns("teaching_resource")
    op.alter_column(
        "teaching_resource",
        "status",
        existing_type=resource_columns["status"]["type"],
        type_=sa.String(32),
        nullable=False,
        server_default=sa.text("'READY'"),
    )

    _add_missing_columns(
        "resource_ai_suggestion",
        (
            sa.Column("user_request", sa.Text(), nullable=True),
            sa.Column("metadata_json", mysql.JSON(), nullable=True),
        ),
    )


def downgrade() -> None:
    # Do not remove populated Mode A data during downgrade.
    pass
