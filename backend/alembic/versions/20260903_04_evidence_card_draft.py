"""Add deterministic Evidence Card draft fields and confirmation state."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260903_04"
down_revision = "20260903_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_evidence_review_strength", table_name="evidence_card")
    op.alter_column(
        "evidence_card",
        "review_status",
        new_column_name="card_status",
        existing_type=sa.String(32),
        existing_nullable=False,
        existing_server_default="DRAFT",
    )
    op.execute(
        "UPDATE evidence_card SET card_status = 'CONFIRMED' "
        "WHERE card_status = 'REVIEWED'"
    )
    op.create_check_constraint(
        "ck_evidence_card_status",
        "evidence_card",
        "card_status IN ('DRAFT', 'CONFIRMED')",
    )
    op.create_index(
        "idx_evidence_card_status_strength",
        "evidence_card",
        ["card_status", "evidence_strength"],
    )
    op.create_unique_constraint(
        "uk_evidence_research_analysis",
        "evidence_card",
        ["research_analysis_id"],
    )
    op.add_column(
        "evidence_card",
        sa.Column("recommended_strategies_json", mysql.JSON(), nullable=True),
    )
    op.add_column(
        "evidence_card",
        sa.Column("implementation_conditions_json", mysql.JSON(), nullable=True),
    )
    op.add_column(
        "evidence_card",
        sa.Column("source_metadata_json", mysql.JSON(), nullable=True),
    )
    op.add_column(
        "evidence_card",
        sa.Column("confirmed_by", mysql.BIGINT(unsigned=True), nullable=True),
    )
    op.add_column(
        "evidence_card",
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_foreign_key(
        "fk_evidence_confirmed_by",
        "evidence_card",
        "sys_user",
        ["confirmed_by"],
        ["id"],
        ondelete="RESTRICT",
        onupdate="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_evidence_confirmed_by",
        "evidence_card",
        type_="foreignkey",
    )
    op.drop_column("evidence_card", "confirmed_at")
    op.drop_column("evidence_card", "confirmed_by")
    op.drop_column("evidence_card", "source_metadata_json")
    op.drop_column("evidence_card", "implementation_conditions_json")
    op.drop_column("evidence_card", "recommended_strategies_json")
    op.drop_constraint(
        "uk_evidence_research_analysis",
        "evidence_card",
        type_="unique",
    )
    op.drop_index(
        "idx_evidence_card_status_strength",
        table_name="evidence_card",
    )
    op.drop_constraint(
        "ck_evidence_card_status",
        "evidence_card",
        type_="check",
    )
    op.execute(
        "UPDATE evidence_card SET card_status = 'REVIEWED' "
        "WHERE card_status = 'CONFIRMED'"
    )
    op.alter_column(
        "evidence_card",
        "card_status",
        new_column_name="review_status",
        existing_type=sa.String(32),
        existing_nullable=False,
        existing_server_default="DRAFT",
    )
    op.create_index(
        "idx_evidence_review_strength",
        "evidence_card",
        ["review_status", "evidence_strength"],
    )
