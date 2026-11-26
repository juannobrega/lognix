"""patterns, analysis_runs, triggers_fired

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

log_level = postgresql.ENUM(
    "error", "warn", "info", "debug", "unknown", name="log_level", create_type=False
)
run_status = postgresql.ENUM("ok", "skipped", "failed", name="run_status", create_type=False)
trigger_type = postgresql.ENUM(
    "error", "docker_event", "anomaly", "manual", name="trigger_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for e in (log_level, run_status, trigger_type):
        e.create(bind, checkfirst=True)
    op.create_table(
        "patterns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "container_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("containers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("level", log_level, nullable=False),
        sa.Column("count_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sample", sa.Text(), nullable=False, server_default=""),
        sa.Column("ignored", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("container_id", "template", name="uq_patterns_container_template"),
    )
    op.create_index("ix_patterns_container_id", "patterns", ["container_id"])
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "container_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("containers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lines_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_lines_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warn_lines_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_patterns_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_called", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ai_duration_ms", sa.Integer(), nullable=True),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manual", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", run_status, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_analysis_runs_container_id", "analysis_runs", ["container_id"])
    op.create_index("ix_analysis_runs_window_end", "analysis_runs", ["window_end"])
    op.create_table(
        "triggers_fired",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_run_id",
            sa.BigInteger(),
            sa.ForeignKey("analysis_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "container_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("containers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", trigger_type, nullable=False),
        sa.Column("reason", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "fired_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("insight_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_lines", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("note", sa.String(255), nullable=True),
    )
    op.create_index("ix_triggers_fired_container_id", "triggers_fired", ["container_id"])
    op.create_index("ix_triggers_fired_insight_id", "triggers_fired", ["insight_id"])
    op.create_index("ix_triggers_fired_fired_at", "triggers_fired", ["fired_at"])


def downgrade() -> None:
    op.drop_table("triggers_fired")
    op.drop_table("analysis_runs")
    op.drop_table("patterns")
    bind = op.get_bind()
    for e in (trigger_type, run_status, log_level):
        e.drop(bind, checkfirst=True)
