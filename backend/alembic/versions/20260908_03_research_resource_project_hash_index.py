"""Index project-local research-resource SHA-256 lookups.

Revision ID: 20260908_03
Revises: 20260908_02
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op


revision = "20260908_03"
down_revision = "20260908_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This intentionally remains a non-unique index: existing production data
    # contains historical duplicate hashes. New uploads are deduplicated by the
    # service under a FOR UPDATE lock without changing that data.
    op.create_index(
        "idx_research_resource_project_sha256",
        "research_resource",
        ["project_id", "sha256"],
        unique=False,
    )
    # The ORM has always required a hash. Align legacy databases which still
    # exposed this column as nullable before relying on it for deduplication.
    op.alter_column(
        "research_resource",
        "sha256",
        existing_type=sa.String(length=64),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "research_resource",
        "sha256",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.drop_index("idx_research_resource_project_sha256", table_name="research_resource")
