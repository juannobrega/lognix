"""ai_providers e ai_models, e provider nas chamadas

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

provider_status = postgresql.ENUM(
    "unknown", "ok", "error", name="provider_status", create_type=False
)


def upgrade() -> None:
    provider_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ai_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credentials_enc", sa.LargeBinary(), nullable=True),
        sa.Column("credential_keys", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("default_model", sa.String(160), nullable=True),
        sa.Column("last_status", provider_status, nullable=False, server_default="unknown"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_providers_priority", "ai_providers", ["priority"])
    op.create_table(
        "ai_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("label", sa.String(160), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column("prompt_usd_per_mtok", sa.Numeric(12, 4), nullable=True),
        sa.Column("completion_usd_per_mtok", sa.Numeric(12, 4), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("provider_id", "model_id", name="uq_ai_models_provider_model"),
    )
    op.create_index("ix_ai_models_provider_id", "ai_models", ["provider_id"])

    op.add_column(
        "ai_calls",
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_providers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_calls", sa.Column("provider_name", sa.String(80), nullable=False, server_default="")
    )
    op.add_column(
        "ai_calls", sa.Column("attempt", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "ai_calls", sa.Column("fell_back", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.create_index("ix_ai_calls_provider_id", "ai_calls", ["provider_id"])
    op.alter_column("ai_calls", "model", type_=sa.String(160))


def downgrade() -> None:
    op.alter_column("ai_calls", "model", type_=sa.String(120))
    op.drop_index("ix_ai_calls_provider_id", "ai_calls")
    for col in ("fell_back", "attempt", "provider_name", "provider_id"):
        op.drop_column("ai_calls", col)
    op.drop_table("ai_models")
    op.drop_table("ai_providers")
    provider_status.drop(op.get_bind(), checkfirst=True)
