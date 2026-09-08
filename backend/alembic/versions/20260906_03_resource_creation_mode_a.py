"""Create persistence tables for resource creation Mode A.

Revision ID: 20260906_03
Revises: 20260906_02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260906_03"
down_revision = "20260906_02"
branch_labels = None
depends_on = None


TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


TABLE_NAMES = (
    "resource_creation_job",
    "teaching_resource",
    "teaching_resource_version",
    "resource_ai_suggestion",
)


def _updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


def upgrade() -> None:
    # The live database may have been provisioned from this exact DDL before
    # Alembic history was restored. Avoid a duplicate-table failure in that case.
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if set(TABLE_NAMES).issubset(existing_tables):
        return

    op.create_table(
        "resource_creation_job",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("project_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("selected_types_json", mysql.JSON(), nullable=True),
        sa.Column("common_settings_json", mysql.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        _updated_at_column(),
        sa.ForeignKeyConstraint(["project_id"], ["course_project.id"], name="fk_resource_creation_job_project", ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], name="fk_resource_creation_job_user", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.CheckConstraint("mode IN ('COURSE_GENERATE', 'RESOURCE_ADAPT')", name="ck_resource_creation_job_mode"),
        **TABLE_OPTIONS,
    )
    op.create_index("idx_resource_creation_job_project", "resource_creation_job", ["project_id"])
    op.create_index("idx_resource_creation_job_user", "resource_creation_job", ["user_id"])
    op.create_index("idx_resource_creation_job_project_status", "resource_creation_job", ["project_id", "status"])

    op.create_table(
        "teaching_resource",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("job_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("project_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("settings_json", mysql.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("current_version_no", mysql.INTEGER(unsigned=True), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        _updated_at_column(),
        sa.ForeignKeyConstraint(["job_id"], ["resource_creation_job.id"], name="fk_teaching_resource_job", ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["course_project.id"], name="fk_teaching_resource_project", ondelete="CASCADE", onupdate="CASCADE"),
        sa.UniqueConstraint("job_id", "resource_type", name="uk_teaching_resource_job_type"),
        sa.CheckConstraint("resource_type IN ('PPT', 'TEACHER_GUIDE', 'WORKSHEET', 'TASK_CARD', 'AI_CASE', 'DISCUSSION', 'ASSESSMENT', 'REFLECTION')", name="ck_teaching_resource_type"),
        **TABLE_OPTIONS,
    )
    op.create_index("idx_teaching_resource_project", "teaching_resource", ["project_id"])
    op.create_index("idx_teaching_resource_job", "teaching_resource", ["job_id"])
    op.create_index("idx_teaching_resource_project_type", "teaching_resource", ["project_id", "resource_type"])

    op.create_table(
        "teaching_resource_version",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("resource_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("version_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("content_json", mysql.JSON(), nullable=False),
        sa.Column("content_html", mysql.LONGTEXT(), nullable=True),
        sa.Column("change_source", sa.String(32), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("created_by", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["resource_id"], ["teaching_resource.id"], name="fk_teaching_resource_version_resource", ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["sys_user.id"], name="fk_teaching_resource_version_created_by", ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("resource_id", "version_no", name="uk_teaching_resource_version"),
        sa.CheckConstraint("change_source IN ('AI', 'TEACHER', 'AI_ACCEPTED')", name="ck_teaching_resource_version_source"),
        **TABLE_OPTIONS,
    )
    op.create_index("idx_teaching_resource_version_resource", "teaching_resource_version", ["resource_id"])
    op.create_index("idx_teaching_resource_version_resource_no", "teaching_resource_version", ["resource_id", "version_no"])

    op.create_table(
        "resource_ai_suggestion",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("resource_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("base_version_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("target_block_key", sa.String(100), nullable=True),
        sa.Column("suggestion_type", sa.String(64), nullable=False),
        sa.Column("issue", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("suggested_content", mysql.LONGTEXT(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("teacher_revision", mysql.LONGTEXT(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["resource_id"], ["teaching_resource.id"], name="fk_resource_ai_suggestion_resource", ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["base_version_id"], ["teaching_resource_version.id"], name="fk_resource_ai_suggestion_version", ondelete="CASCADE", onupdate="CASCADE"),
        sa.CheckConstraint("status IN ('PENDING', 'ACCEPTED', 'REVISED', 'REJECTED')", name="ck_resource_ai_suggestion_status"),
        **TABLE_OPTIONS,
    )
    op.create_index("idx_resource_ai_suggestion_resource", "resource_ai_suggestion", ["resource_id"])
    op.create_index("idx_resource_ai_suggestion_base_version", "resource_ai_suggestion", ["base_version_id"])
    op.create_index("idx_resource_ai_suggestion_resource_status", "resource_ai_suggestion", ["resource_id", "status"])


def downgrade() -> None:
    op.drop_table("resource_ai_suggestion")
    op.drop_table("teaching_resource_version")
    op.drop_table("teaching_resource")
    op.drop_table("resource_creation_job")
