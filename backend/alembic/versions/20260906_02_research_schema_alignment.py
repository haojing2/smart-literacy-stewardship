"""Align research collaboration tables with their ORM contracts.

Revision ID: 20260906_02
Revises: 20260906_01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260906_02"
down_revision = "20260906_01"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> dict[str, dict]:
    return {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _scalar(statement: str) -> int:
    return int(op.get_bind().execute(sa.text(statement)).scalar_one())


def _foreign_keys(table_name: str) -> dict[str, dict]:
    return {
        foreign_key["name"]: foreign_key
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
    }


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        index["name"] for index in inspector.get_indexes(table_name)
    } | {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint["name"]
    }


def _has_duplicate_non_null_values(table_name: str, column_name: str) -> bool:
    return _scalar(
        f"SELECT COUNT(*) FROM ("
        f"SELECT {column_name} FROM {table_name} "
        f"WHERE {column_name} IS NOT NULL "
        f"GROUP BY {column_name} HAVING COUNT(*) > 1"
        f") AS duplicate_values"
    ) > 0


def _has_orphan_references(
    table_name: str, local_column: str, referred_table: str, referred_column: str
) -> bool:
    return _scalar(
        f"SELECT COUNT(*) FROM {table_name} AS child "
        f"LEFT JOIN {referred_table} AS parent "
        f"ON parent.{referred_column} = child.{local_column} "
        f"WHERE child.{local_column} IS NOT NULL "
        f"AND parent.{referred_column} IS NULL"
    ) > 0


def _add_fk_if_missing(
    table_name: str,
    constraint_name: str,
    local_column: str,
    referred_table: str,
    referred_column: str,
) -> None:
    foreign_key = _foreign_keys(table_name).get(constraint_name)
    if foreign_key is not None:
        options = foreign_key.get("options") or {}
        if (
            foreign_key["referred_table"] == referred_table
            and foreign_key["referred_columns"] == [referred_column]
            and options.get("ondelete", "").upper() == "RESTRICT"
            and options.get("onupdate", "").upper() == "CASCADE"
        ):
            return
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")

    op.create_foreign_key(
        constraint_name,
        table_name,
        referred_table,
        [local_column],
        [referred_column],
        ondelete="RESTRICT",
        onupdate="CASCADE",
    )


def upgrade() -> None:
    bind = op.get_bind()
    resource_columns = _columns("research_resource")

    # Preserve legacy file columns while filling the formal fields when they
    # are incomplete. SHA-256 has no legacy source and is never fabricated.
    legacy_mappings = {
        "original_filename": "file_name",
        "storage_key": "file_path",
        "media_type": "mime_type",
        "size_bytes": "file_size",
    }
    for target, legacy in legacy_mappings.items():
        if target in resource_columns and legacy in resource_columns:
            bind.execute(
                sa.text(
                    f"UPDATE research_resource SET {target} = {legacy} "
                    f"WHERE {target} IS NULL AND {legacy} IS NOT NULL"
                )
            )

    # ANALYZED is no longer a valid ORM status. Confirmed resources become
    # REVIEWED; otherwise a successfully extracted resource is TEXT_EXTRACTED.
    bind.execute(
        sa.text(
            "UPDATE research_resource r SET processing_status = 'REVIEWED' "
            "WHERE r.processing_status = 'ANALYZED' AND EXISTS ("
            "SELECT 1 FROM research_analysis a "
            "WHERE a.resource_id = r.id AND a.teacher_confirmed = 1)"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE research_resource SET processing_status = 'TEXT_EXTRACTED' "
            "WHERE processing_status = 'ANALYZED' "
            "AND extracted_text IS NOT NULL AND extracted_text <> ''"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE research_resource SET processing_status = 'FAILED' "
            "WHERE processing_status = 'ANALYZED'"
        )
    )

    required_resource_columns = {
        "original_filename": mysql.VARCHAR(255),
        "storage_key": mysql.VARCHAR(500),
        "media_type": mysql.VARCHAR(100),
        "size_bytes": mysql.BIGINT(unsigned=True),
        "sha256": mysql.VARCHAR(64),
    }
    for name, column_type in required_resource_columns.items():
        if name not in resource_columns:
            continue
        invalid = _scalar(
            f"SELECT COUNT(*) FROM research_resource "
            f"WHERE {name} IS NULL"
            + (f" OR {name} = ''" if name != "size_bytes" else "")
        )
        if invalid == 0:
            op.alter_column(
                "research_resource",
                name,
                existing_type=resource_columns[name]["type"],
                type_=column_type,
                nullable=False,
            )

    if (
        "storage_key" in resource_columns
        and not _has_duplicate_non_null_values("research_resource", "storage_key")
        and "uk_research_resource_storage_key" not in _index_names("research_resource")
    ):
        op.create_unique_constraint(
            "uk_research_resource_storage_key", "research_resource", ["storage_key"]
        )

    analysis_columns = _columns("research_analysis")
    if (
        "structured_data_json" in analysis_columns
        and _scalar(
            "SELECT COUNT(*) FROM research_analysis "
            "WHERE structured_data_json IS NULL"
        ) == 0
        and analysis_columns["structured_data_json"]["nullable"]
    ):
        op.alter_column(
            "research_analysis",
            "structured_data_json",
            existing_type=analysis_columns["structured_data_json"]["type"],
            type_=mysql.JSON(),
            nullable=False,
        )

    session_columns = _columns("research_chat_session")
    session_values_complete = (
        _scalar(
            "SELECT COUNT(*) FROM research_chat_session WHERE resource_id IS NULL"
        ) == 0
        and _scalar(
            "SELECT COUNT(*) FROM research_chat_session "
            "WHERE title IS NULL OR title = ''"
        ) == 0
    )
    if session_values_complete:
        resource_fk = _foreign_keys("research_chat_session").get(
            "fk_research_chat_session_resource"
        )
        if resource_fk is not None:
            options = resource_fk.get("options") or {}
            if (
                options.get("ondelete", "").upper() != "RESTRICT"
                or options.get("onupdate", "").upper() != "CASCADE"
            ):
                op.drop_constraint(
                    "fk_research_chat_session_resource",
                    "research_chat_session",
                    type_="foreignkey",
                )
        op.alter_column(
            "research_chat_session",
            "resource_id",
            existing_type=session_columns["resource_id"]["type"],
            type_=mysql.BIGINT(unsigned=True),
            nullable=False,
        )
        op.alter_column(
            "research_chat_session",
            "title",
            existing_type=session_columns["title"]["type"],
            type_=mysql.VARCHAR(255),
            nullable=False,
        )
        if not _has_orphan_references(
            "research_chat_session", "resource_id", "research_resource", "id"
        ):
            _add_fk_if_missing(
                "research_chat_session",
                "fk_research_chat_session_resource",
                "resource_id",
                "research_resource",
                "id",
            )

    message_columns = _columns("research_chat_message")
    if _scalar(
        "SELECT COUNT(*) FROM research_chat_message WHERE sequence_no IS NULL"
    ) == 0:
        op.alter_column(
            "research_chat_message",
            "sequence_no",
            existing_type=message_columns["sequence_no"]["type"],
            type_=sa.Integer(),
            nullable=False,
        )
    if _scalar(
        "SELECT COUNT(*) FROM research_chat_message WHERE CHAR_LENGTH(role) > 16"
    ) == 0:
        op.alter_column(
            "research_chat_message",
            "role",
            existing_type=message_columns["role"]["type"],
            type_=mysql.VARCHAR(16),
            nullable=False,
        )
    if _scalar(
        "SELECT COUNT(*) FROM research_chat_message "
        "WHERE OCTET_LENGTH(content) > 16777215"
    ) == 0:
        op.alter_column(
            "research_chat_message",
            "content",
            existing_type=message_columns["content"]["type"],
            type_=mysql.MEDIUMTEXT(),
            nullable=False,
        )
    if (
        _scalar(
            "SELECT COUNT(*) FROM (SELECT session_id, sequence_no "
            "FROM research_chat_message GROUP BY session_id, sequence_no "
            "HAVING COUNT(*) > 1) AS duplicate_sequences"
        ) == 0
        and "uk_research_message_sequence" not in _index_names("research_chat_message")
    ):
        op.create_unique_constraint(
            "uk_research_message_sequence",
            "research_chat_message",
            ["session_id", "sequence_no"],
        )

    # Evidence Card legacy review_status is deliberately retained. Add only
    # the ORM-backed relations and lookup constraints that are currently absent.
    if (
        not _has_duplicate_non_null_values("evidence_card", "research_analysis_id")
        and "uk_evidence_research_analysis" not in _index_names("evidence_card")
    ):
        op.create_unique_constraint(
            "uk_evidence_research_analysis",
            "evidence_card",
            ["research_analysis_id"],
        )
    if "idx_evidence_research_analysis" not in _index_names("evidence_card"):
        op.create_index(
            "idx_evidence_research_analysis",
            "evidence_card",
            ["research_analysis_id"],
        )
    if not _has_orphan_references(
        "evidence_card", "research_analysis_id", "research_analysis", "id"
    ):
        _add_fk_if_missing(
            "evidence_card",
            "fk_evidence_research_analysis",
            "research_analysis_id",
            "research_analysis",
            "id",
        )
    if not _has_orphan_references(
        "evidence_card", "confirmed_by", "sys_user", "id"
    ):
        _add_fk_if_missing(
            "evidence_card",
            "fk_evidence_confirmed_by",
            "confirmed_by",
            "sys_user",
            "id",
        )


def downgrade() -> None:
    # Legacy data and compatibility fields are intentionally retained.
    pass
