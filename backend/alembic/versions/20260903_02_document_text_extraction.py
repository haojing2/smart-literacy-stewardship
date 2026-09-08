"""Add document text extraction states and error details."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260903_02"
down_revision = "20260903_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("research_resource")}
    checks = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("research_resource")
    }

    if "ck_research_resource_status" in checks:
        op.drop_constraint(
            "ck_research_resource_status",
            "research_resource",
            type_="check",
        )

    bind.execute(
        sa.text(
            "UPDATE research_resource "
            "SET status = CASE "
            "WHEN status = 'EXTRACTING' THEN 'TEXT_EXTRACTING' "
            "WHEN status = 'READY' THEN 'TEXT_EXTRACTED' "
            "ELSE status END"
        )
    )

    if "extraction_error" in columns and "error_message" not in columns:
        op.alter_column(
            "research_resource",
            "extraction_error",
            new_column_name="error_message",
            existing_type=sa.Text(),
            existing_nullable=True,
        )
    elif "error_message" not in columns:
        op.add_column(
            "research_resource",
            sa.Column("error_message", sa.Text(), nullable=True),
        )

    op.alter_column(
        "research_resource",
        "extracted_text",
        existing_type=mysql.MEDIUMTEXT(),
        type_=mysql.LONGTEXT(),
        existing_nullable=True,
    )
    op.create_check_constraint(
        "ck_research_resource_status",
        "research_resource",
        "status IN ('UPLOADED', 'TEXT_EXTRACTING', 'TEXT_EXTRACTED', 'FAILED')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_constraint(
        "ck_research_resource_status",
        "research_resource",
        type_="check",
    )
    bind.execute(
        sa.text(
            "UPDATE research_resource "
            "SET status = CASE "
            "WHEN status = 'TEXT_EXTRACTING' THEN 'EXTRACTING' "
            "WHEN status = 'TEXT_EXTRACTED' THEN 'READY' "
            "ELSE status END"
        )
    )
    op.alter_column(
        "research_resource",
        "error_message",
        new_column_name="extraction_error",
        existing_type=sa.Text(),
        existing_nullable=True,
    )
    op.create_check_constraint(
        "ck_research_resource_status",
        "research_resource",
        "status IN ('UPLOADED', 'EXTRACTING', 'READY', 'FAILED')",
    )
