"""Deduplicação de insights: chave, contagem e última ocorrência. Ver ADR 016.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("insights", sa.Column("dedupe_key", sa.String(80), nullable=True))
    op.add_column(
        "insights", sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("insights", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    # Os insights que já existem passam a contar a partir de agora.
    op.execute("UPDATE insights SET last_seen_at = created_at WHERE last_seen_at IS NULL")
    # O índice serve exatamente à pergunta do ciclo: "já existe insight ativo para esta chave
    # neste container?". Sem o status na chave, um insight já visto bloquearia um aviso novo.
    op.create_index(
        "ix_insights_dedupe",
        "insights",
        ["container_id", "dedupe_key", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_insights_dedupe", "insights")
    for coluna in ("last_seen_at", "occurrences", "dedupe_key"):
        op.drop_column("insights", coluna)
