"""Persist verified project-retrieval provenance on evidence cards.

Revision ID: 20260908_06
Revises: 20260908_05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "20260908_06"
down_revision = "20260908_05"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_columns("evidence_card")
    }


def _unique_names() -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_unique_constraints("evidence_card")
        if item.get("name")
    }


def _foreign_key_names() -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_foreign_keys("evidence_card")
        if item.get("name")
    }


def _index_names() -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_indexes("evidence_card")
        if item.get("name")
    }


def upgrade() -> None:
    columns = _columns()
    additions = (
        ("project_id", sa.Column("project_id", mysql.BIGINT(unsigned=True), nullable=True)),
        ("source_file_id", sa.Column("source_file_id", mysql.BIGINT(unsigned=True), nullable=True)),
        ("source_chunk_id", sa.Column("source_chunk_id", sa.String(length=64), nullable=True)),
        ("source_retrieval_score", sa.Column("source_retrieval_score", sa.Float(), nullable=True)),
        ("source_message_id", sa.Column("source_message_id", mysql.BIGINT(unsigned=True), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("evidence_card", column)

    # Preserve old cards while making the new project lookup available.
    op.execute(
        "UPDATE evidence_card AS card "
        "JOIN research_analysis AS analysis ON analysis.id = card.research_analysis_id "
        "SET card.project_id = analysis.project_id "
        "WHERE card.project_id IS NULL"
    )

    unique_names = _unique_names()
    if "uk_evidence_research_analysis" in unique_names:
        op.drop_constraint("uk_evidence_research_analysis", "evidence_card", type_="unique")
    if "uk_evidence_project_source_chunk" not in _unique_names():
        op.create_unique_constraint(
            "uk_evidence_project_source_chunk",
            "evidence_card",
            ["project_id", "source_chunk_id"],
        )

    foreign_keys = _foreign_key_names()
    if "fk_evidence_card_project" not in foreign_keys:
        op.create_foreign_key(
            "fk_evidence_card_project", "evidence_card", "course_project",
            ["project_id"], ["id"], ondelete="RESTRICT", onupdate="CASCADE",
        )
    if "fk_evidence_card_source_file" not in foreign_keys:
        op.create_foreign_key(
            "fk_evidence_card_source_file", "evidence_card", "research_resource",
            ["source_file_id"], ["id"], ondelete="RESTRICT", onupdate="CASCADE",
        )
    if "fk_evidence_card_source_message" not in foreign_keys:
        op.create_foreign_key(
            "fk_evidence_card_source_message", "evidence_card", "research_chat_message",
            ["source_message_id"], ["id"], ondelete="RESTRICT", onupdate="CASCADE",
        )
    if "idx_evidence_source_message" not in _index_names():
        op.create_index("idx_evidence_source_message", "evidence_card", ["source_message_id"])


def downgrade() -> None:
    # Keep provenance so historical cards remain traceable after a rollback.
    pass
