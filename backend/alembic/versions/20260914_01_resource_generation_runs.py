"""Add progressive resource generation runs and parts.

Revision ID: 20260914_01
Revises: 20260909_01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "20260914_01"
down_revision = "20260909_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "resource_generation_run" not in tables:
        op.create_table(
            "resource_generation_run",
            sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
            sa.Column("job_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("resource_creation_job.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False),
            sa.Column("project_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("course_project.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False),
            sa.Column("user_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("sys_user.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
            sa.Column("selected_types_json", mysql.JSON(), nullable=False),
            sa.Column("normalized_context_json", mysql.JSON(), nullable=False),
            sa.Column("context_fallback", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("total_parts", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"),
            sa.Column("ready_parts", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"),
            sa.Column("failed_parts", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime()),
            sa.CheckConstraint("status IN ('PENDING','GENERATING','PARTIAL_FAILED','READY','FAILED','FAILED_CONFIG')", name="ck_resource_generation_run_status"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_resource_generation_run_job", "resource_generation_run", ["job_id"])
        op.create_index("idx_resource_generation_run_project_user", "resource_generation_run", ["project_id", "user_id"])
        op.create_index("idx_resource_generation_run_status", "resource_generation_run", ["status"])
    if "resource_generation_part" not in tables:
        op.create_table(
            "resource_generation_part",
            sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
            sa.Column("run_id", mysql.BIGINT(unsigned=True), sa.ForeignKey("resource_generation_run.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False),
            sa.Column("resource_type", sa.String(32), nullable=False),
            sa.Column("part_key", sa.String(100), nullable=False),
            sa.Column("section", sa.String(64), nullable=False),
            sa.Column("sequence_no", mysql.INTEGER(unsigned=True), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
            sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("dependencies_json", mysql.JSON(), nullable=False),
            sa.Column("spec_json", mysql.JSON(), nullable=False),
            sa.Column("content_json", mysql.JSON()),
            sa.Column("attempt_count", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"),
            sa.Column("model_id", sa.String(128)),
            sa.Column("error_code", sa.String(64)),
            sa.Column("error_message", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            sa.UniqueConstraint("run_id", "resource_type", "part_key", name="uk_resource_generation_part_key"),
            sa.CheckConstraint("status IN ('PENDING','GENERATING','READY','FAILED')", name="ck_resource_generation_part_status"),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_unicode_ci",
        )
        op.create_index("idx_resource_generation_part_run", "resource_generation_part", ["run_id"])
        op.create_index("idx_resource_generation_part_run_type", "resource_generation_part", ["run_id", "resource_type"])
        op.create_index("idx_resource_generation_part_run_status", "resource_generation_part", ["run_id", "status"])
        op.create_index("idx_resource_generation_part_run_type_sequence", "resource_generation_part", ["run_id", "resource_type", "sequence_no"])


def downgrade() -> None:
    op.drop_table("resource_generation_part")
    op.drop_table("resource_generation_run")
