"""Track research-analysis generation independently from review status.

Revision ID: 20260909_01
Revises: 20260908_06
"""

import json

import sqlalchemy as sa
from alembic import op


revision = "20260909_01"
down_revision = "20260908_06"
branch_labels = None
depends_on = None


def _is_empty_analysis(value: object) -> bool:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return False
    if not isinstance(value, dict):
        return False
    meaningful = (
        "research_subjects", "research_topics", "ai_literacy_dimensions",
        "teaching_strategies", "intervention_duration", "assessment_tools",
        "main_findings", "limitations", "teaching_implications", "source_excerpt",
    )
    return not any(value.get(field) for field in meaningful)


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("research_analysis")}
    if "generation_status" not in columns:
        op.add_column(
            "research_analysis",
            sa.Column("generation_status", sa.String(16), nullable=False, server_default="READY"),
        )

    rows = bind.execute(sa.text(
        "SELECT id, resource_id, teacher_confirmed, structured_data_json "
        "FROM research_analysis WHERE resource_id IS NOT NULL"
    )).mappings()
    failed_ids = [
        int(row["id"])
        for row in rows
        if not bool(row["teacher_confirmed"]) and _is_empty_analysis(row["structured_data_json"])
    ]
    if failed_ids:
        bind.execute(
            sa.text("UPDATE research_analysis SET generation_status='FAILED' WHERE id IN :ids")
            .bindparams(sa.bindparam("ids", expanding=True)),
            {"ids": failed_ids},
        )

    checks = {item["name"] for item in sa.inspect(bind).get_check_constraints("research_analysis")}
    if "ck_research_analysis_generation_status" not in checks:
        op.create_check_constraint(
            "ck_research_analysis_generation_status",
            "research_analysis",
            "generation_status IN ('PENDING', 'READY', 'FAILED')",
        )


def downgrade() -> None:
    op.drop_constraint(
        "ck_research_analysis_generation_status", "research_analysis", type_="check"
    )
    op.drop_column("research_analysis", "generation_status")
