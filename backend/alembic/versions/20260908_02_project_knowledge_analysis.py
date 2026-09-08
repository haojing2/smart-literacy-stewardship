"""Allow research analyses and evidence cards to originate from project knowledge chat.

Revision ID: 20260908_02
Revises: 20260908_01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260908_02"
down_revision = "20260908_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("research_analysis", "resource_id", existing_type=mysql.BIGINT(unsigned=True), nullable=True)
    op.add_column("research_analysis", sa.Column("session_id", mysql.BIGINT(unsigned=True), nullable=True))
    op.create_foreign_key(
        "fk_research_analysis_session", "research_analysis", "research_chat_session",
        ["session_id"], ["id"], ondelete="RESTRICT", onupdate="CASCADE",
    )
    op.create_unique_constraint("uk_research_analysis_session_version", "research_analysis", ["session_id", "version"])
    op.create_index("idx_research_analysis_session_status", "research_analysis", ["session_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_research_analysis_session_status", table_name="research_analysis")
    op.drop_constraint("uk_research_analysis_session_version", "research_analysis", type_="unique")
    op.drop_constraint("fk_research_analysis_session", "research_analysis", type_="foreignkey")
    op.drop_column("research_analysis", "session_id")
    op.alter_column("research_analysis", "resource_id", existing_type=mysql.BIGINT(unsigned=True), nullable=False)
