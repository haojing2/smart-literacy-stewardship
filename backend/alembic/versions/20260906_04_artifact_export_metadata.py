"""Add final-export metadata to artifact without rewriting legacy rows.

Revision ID: 20260906_04
Revises: 20260906_03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260906_04"
down_revision = "20260906_03"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("artifact")
    }


def _index_names() -> set[str]:
    return {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("artifact")
    }


def _foreign_key_names() -> set[str]:
    return {
        foreign_key["name"]
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys("artifact")
    }


def upgrade() -> None:
    new_columns = (
        sa.Column("resource_version_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("file_format", sa.String(16), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size", mysql.BIGINT(unsigned=True), nullable=True),
    )
    existing_columns = _columns()
    for column in new_columns:
        if column.name not in existing_columns:
            op.add_column("artifact", column)

    if "idx_artifact_resource_version" not in _index_names():
        op.create_index(
            "idx_artifact_resource_version", "artifact", ["resource_version_id"]
        )
    if "idx_artifact_project_type" not in _index_names():
        op.create_index(
            "idx_artifact_project_type",
            "artifact",
            ["project_id", "artifact_type", "version"],
        )
    if "fk_artifact_resource_version" not in _foreign_key_names():
        op.create_foreign_key(
            "fk_artifact_resource_version",
            "artifact",
            "teaching_resource_version",
            ["resource_version_id"],
            ["id"],
            ondelete="SET NULL",
            onupdate="CASCADE",
        )


def downgrade() -> None:
    # Export metadata may already be referenced by delivered files; retain it.
    pass
