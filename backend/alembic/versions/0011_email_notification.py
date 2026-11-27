"""Tipo de notificação para falha de envio de e-mail. Ver ADR 020.

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `IF NOT EXISTS` porque `ALTER TYPE ... ADD VALUE` não é reversível: se a migração rodar
    # duas vezes num banco já migrado à mão, ela não pode quebrar.
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'email_failed'")


def downgrade() -> None:
    # O Postgres não remove valor de enum. Deixar o valor para trás é inofensivo — nenhuma
    # linha o usa depois que o código que o escrevia saiu — e fingir que removemos seria pior.
    pass
