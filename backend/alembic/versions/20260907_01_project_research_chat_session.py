"""Allow project-level research chat sessions without a research resource.

Revision ID: 20260907_01
Revises: 20260906_05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260907_01"
down_revision = "20260906_05"
branch_labels = None
depends_on = None


def _resource_foreign_key_is_present() -> bool:
    for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(
        "research_chat_session"
    ):
        if (
            foreign_key.get("referred_table") == "research_resource"
            and foreign_key.get("constrained_columns") == ["resource_id"]
            and foreign_key.get("referred_columns") == ["id"]
        ):
            return True
    return False


def upgrade() -> None:
    # ALTER COLUMN preserves the existing FK; assert it first so a damaged
    # schema is never silently migrated into an unreferenced resource id.
    if not _resource_foreign_key_is_present():
        raise RuntimeError(
            "research_chat_session.resource_id foreign key is missing; migration aborted"
        )
    columns = {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns("research_chat_session")
    }
    if "resource_id" in columns and not columns["resource_id"]["nullable"]:
        op.alter_column(
            "research_chat_session",
            "resource_id",
            existing_type=columns["resource_id"]["type"],
            type_=mysql.BIGINT(unsigned=True),
            nullable=True,
        )


def downgrade() -> None:
    null_sessions = int(
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM research_chat_session WHERE resource_id IS NULL"
            )
        )
        .scalar_one()
    )
    if null_sessions:
        raise RuntimeError(
            "Cannot restore NOT NULL resource_id while project-level chat sessions exist"
        )
    columns = {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns("research_chat_session")
    }
    if "resource_id" in columns and columns["resource_id"]["nullable"]:
        op.alter_column(
            "research_chat_session",
            "resource_id",
            existing_type=columns["resource_id"]["type"],
            type_=mysql.BIGINT(unsigned=True),
            nullable=False,
        )
