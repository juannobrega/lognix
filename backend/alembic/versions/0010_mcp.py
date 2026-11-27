"""Chaves e registro de chamadas do servidor MCP. Ver ADR 017.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # A verificação busca pelo prefixo antes de conferir o hash: sem índice, cada chamada MCP
    # faria varredura na tabela.
    op.create_index("ix_mcp_keys_prefix", "mcp_keys", ["prefix"])

    op.create_table(
        "mcp_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "key_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mcp_keys.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("key_name", sa.String(80), nullable=False, server_default=""),
        sa.Column("tool", sa.String(80), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_mcp_calls_key_id", "mcp_calls", ["key_id"])
    op.create_index("ix_mcp_calls_tool", "mcp_calls", ["tool"])


def downgrade() -> None:
    op.drop_table("mcp_calls")
    op.drop_index("ix_mcp_keys_prefix", "mcp_keys")
    op.drop_table("mcp_keys")
