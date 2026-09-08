"""Ensure all research-chat messages can carry optional metadata.

Revision ID: 20260908_05
Revises: 20260908_04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "20260908_05"
down_revision = "20260908_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("research_chat_message")
    }
    if "metadata_json" not in columns:
        op.add_column(
            "research_chat_message",
            sa.Column("metadata_json", mysql.JSON(), nullable=True),
        )


def downgrade() -> None:
    # Existing deployments may have introduced this extension field before the
    # migration chain. Retain it to keep all historical messages readable.
    pass
