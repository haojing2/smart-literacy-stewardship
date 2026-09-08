"""Version analysis provenance and teacher review state."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260903_03"
down_revision = "20260903_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_research_resource_status",
        "research_resource",
        type_="check",
    )
    op.drop_index(
        "idx_research_resource_project_status",
        table_name="research_resource",
    )
    op.alter_column(
        "research_resource",
        "status",
        new_column_name="processing_status",
        existing_type=sa.String(32),
        existing_nullable=False,
        existing_server_default="UPLOADED",
    )
    op.create_index(
        "idx_research_resource_project_processing_status",
        "research_resource",
        ["project_id", "processing_status"],
    )
    op.create_check_constraint(
        "ck_research_resource_status",
        "research_resource",
        "processing_status IN "
        "('UPLOADED', 'TEXT_EXTRACTING', 'TEXT_EXTRACTED', 'FAILED', 'REVIEWED')",
    )

    op.add_column(
        "research_analysis",
        sa.Column("field_sources_json", mysql.JSON(), nullable=True),
    )
    op.add_column(
        "research_analysis",
        sa.Column(
            "teacher_confirmed",
            mysql.TINYINT(1),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "research_analysis",
        sa.Column("teacher_confirmed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_analysis", "teacher_confirmed_at")
    op.drop_column("research_analysis", "teacher_confirmed")
    op.drop_column("research_analysis", "field_sources_json")

    op.drop_constraint(
        "ck_research_resource_status",
        "research_resource",
        type_="check",
    )
    op.drop_index(
        "idx_research_resource_project_processing_status",
        table_name="research_resource",
    )
    op.execute(
        "UPDATE research_resource SET processing_status = 'TEXT_EXTRACTED' "
        "WHERE processing_status = 'REVIEWED'"
    )
    op.alter_column(
        "research_resource",
        "processing_status",
        new_column_name="status",
        existing_type=sa.String(32),
        existing_nullable=False,
        existing_server_default="UPLOADED",
    )
    op.create_index(
        "idx_research_resource_project_status",
        "research_resource",
        ["project_id", "status"],
    )
    op.create_check_constraint(
        "ck_research_resource_status",
        "research_resource",
        "status IN ('UPLOADED', 'TEXT_EXTRACTING', 'TEXT_EXTRACTED', 'FAILED')",
    )
