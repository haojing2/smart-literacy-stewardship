"""Bind one Evidence Card to each research chat session."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260903_05"
down_revision = "20260903_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_research_resource_status", "research_resource", type_="check")
    op.create_check_constraint(
        "ck_research_resource_status",
        "research_resource",
        "processing_status IN ('UPLOADED', 'TEXT_EXTRACTING', 'TEXT_EXTRACTED', "
        "'FAILED', 'REVIEWED', 'CARD_READY')",
    )
    op.add_column(
        "research_chat_session",
        sa.Column("evidence_card_id", mysql.BIGINT(unsigned=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_research_chat_session_evidence_card",
        "research_chat_session",
        "evidence_card",
        ["evidence_card_id"],
        ["id"],
        ondelete="RESTRICT",
        onupdate="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_research_chat_session_evidence_card",
        "research_chat_session",
        type_="foreignkey",
    )
    op.drop_column("research_chat_session", "evidence_card_id")
    op.drop_constraint("ck_research_resource_status", "research_resource", type_="check")
    op.execute(
        "UPDATE research_resource SET processing_status = 'REVIEWED' "
        "WHERE processing_status = 'CARD_READY'"
    )
    op.create_check_constraint(
        "ck_research_resource_status",
        "research_resource",
        "processing_status IN ('UPLOADED', 'TEXT_EXTRACTING', 'TEXT_EXTRACTED', "
        "'FAILED', 'REVIEWED')",
    )
