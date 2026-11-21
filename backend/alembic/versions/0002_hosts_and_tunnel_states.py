"""hosts e tunnel_states

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ssh_auth_method = postgresql.ENUM(
    "key", "key_passphrase", "password", name="ssh_auth_method", create_type=False
)
runtime = postgresql.ENUM("docker", name="runtime", create_type=False)
host_status = postgresql.ENUM(
    "pending",
    "connected",
    "disconnected",
    "error",
    "removed",
    name="host_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    ssh_auth_method.create(bind, checkfirst=True)
    runtime.create(bind, checkfirst=True)
    host_status.create(bind, checkfirst=True)
    op.create_table(
        "hosts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(63), nullable=False, unique=True),
        sa.Column("address", sa.String(253), nullable=False),
        sa.Column("ssh_port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("ssh_user", sa.String(64), nullable=False),
        sa.Column("ssh_auth_method", ssh_auth_method, nullable=False),
        sa.Column("ssh_private_key_enc", sa.LargeBinary(), nullable=True),
        sa.Column("ssh_key_passphrase_enc", sa.LargeBinary(), nullable=True),
        sa.Column("ssh_password_enc", sa.LargeBinary(), nullable=True),
        sa.Column("ssh_host_key_fingerprint", sa.String(120), nullable=True),
        sa.Column("runtime", runtime, nullable=False, server_default="docker"),
        sa.Column("docker_version", sa.String(40), nullable=True),
        sa.Column("status", host_status, nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "tunnel_states",
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hosts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("socket_path", sa.String(255), nullable=True),
        sa.Column("connected_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconnect_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("tunnel_states")
    op.drop_table("hosts")
    bind = op.get_bind()
    host_status.drop(bind, checkfirst=True)
    runtime.drop(bind, checkfirst=True)
    ssh_auth_method.drop(bind, checkfirst=True)
