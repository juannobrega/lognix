"""docker_events, host_events, notifications

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

docker_event_type = postgresql.ENUM(
    "start",
    "die",
    "oom",
    "restart",
    "kill",
    "stop",
    "pause",
    "unpause",
    "health_status",
    "destroy",
    "redeploy",
    name="docker_event_type",
    create_type=False,
)
host_event_type = postgresql.ENUM(
    "connected",
    "disconnected",
    "new_container",
    "container_removed",
    "inventory_synced",
    "events_stream_restarted",
    "error",
    name="host_event_type",
    create_type=False,
)
notification_type = postgresql.ENUM(
    "new_container",
    "host_disconnected",
    "host_reconnected",
    "fingerprint_changed",
    "alloy_reload_failed",
    "events_stream_failed",
    "analysis_skipped",
    "ai_error",
    "github_error",
    name="notification_type",
    create_type=False,
)
notification_status = postgresql.ENUM("new", "seen", name="notification_status", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (docker_event_type, host_event_type, notification_type, notification_status):
        enum.create(bind, checkfirst=True)
    op.add_column(
        "containers", sa.Column("env", postgresql.JSONB(), nullable=False, server_default="{}")
    )
    op.create_table(
        "docker_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "container_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("containers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", docker_event_type, nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("previous_image", sa.String(512), nullable=True),
        sa.Column("new_image", sa.String(512), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_docker_events_container_id", "docker_events", ["container_id"])
    op.create_index("ix_docker_events_occurred_at", "docker_events", ["occurred_at"])
    op.create_table(
        "host_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hosts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", host_event_type, nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_host_events_host_id", "host_events", ["host_id"])
    op.create_index("ix_host_events_occurred_at", "host_events", ["occurred_at"])
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", notification_type, nullable=False),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hosts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "container_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("containers.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", notification_status, nullable=False, server_default="new"),
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
    op.create_index("ix_notifications_host_id", "notifications", ["host_id"])
    op.create_index("ix_notifications_container_id", "notifications", ["container_id"])
    op.create_index("ix_notifications_status", "notifications", ["status"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("host_events")
    op.drop_table("docker_events")
    op.drop_column("containers", "env")
    bind = op.get_bind()
    for enum in (notification_status, notification_type, host_event_type, docker_event_type):
        enum.drop(bind, checkfirst=True)
