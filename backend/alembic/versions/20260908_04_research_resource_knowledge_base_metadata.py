"""Add local knowledge-base metadata to project research files.

Revision ID: 20260908_04
Revises: 20260908_03
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op


revision = "20260908_04"
down_revision = "20260908_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_resource",
        sa.Column("file_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "research_resource",
        sa.Column("parsed_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "research_resource",
        sa.Column(
            "index_status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "research_resource",
        sa.Column("parse_error", sa.Text(), nullable=True),
    )

    # Keep existing uploaded-file records queryable through the new metadata
    # without changing their storage or processing behavior.
    op.execute(
        "UPDATE research_resource "
        "SET file_hash = sha256 "
        "WHERE file_hash IS NULL AND sha256 IS NOT NULL"
    )
    op.create_index(
        "idx_research_resource_project_index_status",
        "research_resource",
        ["project_id", "index_status"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_research_resource_index_status",
        "research_resource",
        "index_status IN ('pending', 'parsing', 'indexing', 'ready', 'error')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_research_resource_index_status",
        "research_resource",
        type_="check",
    )
    op.drop_index(
        "idx_research_resource_project_index_status",
        table_name="research_resource",
    )
    op.drop_column("research_resource", "parse_error")
    op.drop_column("research_resource", "index_status")
    op.drop_column("research_resource", "parsed_path")
    op.drop_column("research_resource", "file_hash")
