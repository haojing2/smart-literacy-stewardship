"""Add the research collaboration database layer."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260903_01"
down_revision = "20260827_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_resource",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("project_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="UPLOADED"),
        sa.Column("extracted_text", mysql.MEDIUMTEXT(), nullable=True),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], ["course_project.id"], name="fk_research_resource_project", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_research_resource_user", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("storage_key", name="uk_research_resource_storage_key"),
        sa.CheckConstraint("status IN ('UPLOADED', 'EXTRACTING', 'READY', 'FAILED')", name="ck_research_resource_status"),
    )
    op.create_index("idx_research_resource_owner_project", "research_resource", ["user_id", "project_id"])
    op.create_index("idx_research_resource_project_status", "research_resource", ["project_id", "status"])

    op.create_table(
        "research_analysis",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("resource_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("structured_data_json", mysql.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["resource_id"], ["research_resource.id"], name="fk_research_analysis_resource", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("resource_id", "version", name="uk_research_analysis_version"),
        sa.CheckConstraint("version > 0", name="ck_research_analysis_version_positive"),
        sa.CheckConstraint("status IN ('DRAFT', 'VALIDATED')", name="ck_research_analysis_status"),
    )
    op.create_index("idx_research_analysis_resource_status", "research_analysis", ["resource_id", "status"])

    op.create_table(
        "research_chat_session",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("resource_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["resource_id"], ["research_resource.id"], name="fk_research_chat_session_resource", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="ck_research_chat_session_status"),
    )
    op.create_index("idx_research_chat_session_resource", "research_chat_session", ["resource_id"])

    op.create_table(
        "research_chat_message",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("session_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("content", mysql.MEDIUMTEXT(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["research_chat_session.id"], name="fk_research_chat_message_session", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("session_id", "sequence_no", name="uk_research_message_sequence"),
        sa.CheckConstraint("role IN ('USER', 'SYSTEM', 'ASSISTANT')", name="ck_research_chat_message_role"),
        sa.CheckConstraint("sequence_no > 0", name="ck_research_chat_message_sequence_positive"),
    )
    op.create_index("idx_research_chat_message_session", "research_chat_message", ["session_id"])

    op.add_column("evidence_card", sa.Column("research_analysis_id", mysql.BIGINT(unsigned=True), nullable=True))
    op.create_index("idx_evidence_research_analysis", "evidence_card", ["research_analysis_id"])
    op.create_foreign_key(
        "fk_evidence_research_analysis",
        "evidence_card",
        "research_analysis",
        ["research_analysis_id"],
        ["id"],
        ondelete="RESTRICT",
        onupdate="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_evidence_research_analysis", "evidence_card", type_="foreignkey")
    op.drop_index("idx_evidence_research_analysis", table_name="evidence_card")
    op.drop_column("evidence_card", "research_analysis_id")
    op.drop_table("research_chat_message")
    op.drop_table("research_chat_session")
    op.drop_table("research_analysis")
    op.drop_table("research_resource")
