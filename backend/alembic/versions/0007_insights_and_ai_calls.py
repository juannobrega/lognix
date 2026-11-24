"""insights e ai_calls

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

severity = postgresql.ENUM(
    "critical", "high", "medium", "low", "info", name="severity", create_type=False
)
insight_status = postgresql.ENUM("new", "seen", name="insight_status", create_type=False)
ai_purpose = postgresql.ENUM(
    "analyze", "code_diagnosis", "issue_text", "test", name="ai_purpose", create_type=False
)
ai_call_status = postgresql.ENUM("ok", "error", name="ai_call_status", create_type=False)
cost_source = postgresql.ENUM(
    "provider", "estimated", "unknown", name="cost_source", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for e in (severity, insight_status, ai_purpose, ai_call_status, cost_source):
        e.create(bind, checkfirst=True)
    op.create_table(
        "insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "container_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("containers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trigger_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("triggers_fired.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("severity", severity, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("probable_cause", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False),
        sa.Column("needs_code", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("code_diagnosis", postgresql.JSONB(), nullable=True),
        sa.Column("context_truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sent_context", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", insight_status, nullable=False, server_default="new"),
        sa.Column(
            "seen_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_insights_container_id", "insights", ["container_id"])
    op.create_index("ix_insights_status", "insights", ["status"])
    op.create_index("ix_insights_created_at", "insights", ["created_at"])
    op.create_table(
        "ai_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "trigger_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("triggers_fired.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "insight_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("insights.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "container_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("containers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(40), nullable=False, server_default="openrouter"),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("purpose", ai_purpose, nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("cost_source", cost_source, nullable=False, server_default="unknown"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("schema_retry", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", ai_call_status, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_ai_calls_container_id", "ai_calls", ["container_id"])
    op.create_index("ix_ai_calls_created_at", "ai_calls", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_calls")
    op.drop_table("insights")
    bind = op.get_bind()
    for e in (cost_source, ai_call_status, ai_purpose, insight_status, severity):
        e.drop(bind, checkfirst=True)
