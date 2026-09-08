"""Persist bounded multi-turn research-chat context summaries.

Revision ID: 20260908_01
Revises: 20260907_01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260908_01"
down_revision = "20260907_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_chat_session",
        sa.Column("conversation_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "research_chat_session",
        sa.Column(
            "conversation_summary_through_sequence_no",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("research_chat_session", "conversation_summary_through_sequence_no")
    op.drop_column("research_chat_session", "conversation_summary")
