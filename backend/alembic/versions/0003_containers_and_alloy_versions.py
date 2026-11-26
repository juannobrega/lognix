"""containers e alloy_config_versions

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

container_state = postgresql.ENUM(
    "created",
    "running",
    "restarting",
    "paused",
    "exited",
    "dead",
    "removed",
    name="container_state",
    create_type=False,
)


def upgrade() -> None:
    container_state.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "containers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hosts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("docker_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("image", sa.String(512), nullable=False, server_default=""),
        sa.Column("image_digest", sa.String(128), nullable=True),
        sa.Column("compose_project", sa.String(255), nullable=True),
        sa.Column("compose_service", sa.String(255), nullable=True),
        sa.Column("labels", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("state", container_state, nullable=False),
        sa.Column("monitored", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("monitored_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("host_id", "docker_id", name="uq_containers_host_docker"),
    )
    op.create_index("ix_containers_host_id", "containers", ["host_id"])
    op.create_table(
        "alloy_config_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column(
            "applied_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("reload_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("alloy_config_versions")
    op.drop_table("containers")
    container_state.drop(op.get_bind(), checkfirst=True)
