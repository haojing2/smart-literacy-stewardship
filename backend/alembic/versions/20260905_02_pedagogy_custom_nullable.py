"""Allow project-only custom pedagogy without a global method row.

Revision ID: 20260905_02
Revises: 20260905_01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260905_02"
down_revision = "20260905_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    column = next(
        item for item in sa.inspect(op.get_bind()).get_columns("project_pedagogy")
        if item["name"] == "primary_method_id"
    )
    if not column["nullable"]:
        op.alter_column(
            "project_pedagogy",
            "primary_method_id",
            existing_type=mysql.BIGINT(unsigned=True),
            nullable=True,
        )


def downgrade() -> None:
    # Custom strategies are retained; a destructive NOT NULL rollback is unsafe.
    pass
