"""Add synthetic generation run ledger.

Revision ID: 20260716_0002
Revises: 20260716_0001
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0002"
down_revision: str | None = "20260716_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the generation-run audit and idempotency ledger."""
    op.create_table(
        "synthetic_generation_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("generator_version", sa.String(length=20), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_case_count", sa.Integer(), nullable=False),
        sa.Column("generated_case_count", sa.Integer(), nullable=False),
        sa.Column("generated_event_count", sa.Integer(), nullable=False),
        sa.Column(
            "configuration_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "manifest_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("dataset_fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="valid_status",
        ),
        sa.CheckConstraint(
            "requested_case_count > 0",
            name="positive_requested_case_count",
        ),
        sa.CheckConstraint(
            "generated_case_count >= 0",
            name="nonnegative_generated_case_count",
        ),
        sa.CheckConstraint(
            "generated_event_count >= 0",
            name="nonnegative_generated_event_count",
        ),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_synthetic_generation_runs_started_at",
        "synthetic_generation_runs",
        ["started_at"],
    )
    op.create_index(
        "ix_synthetic_generation_runs_status",
        "synthetic_generation_runs",
        ["status"],
    )


def downgrade() -> None:
    """Remove the synthetic generation-run ledger."""
    op.drop_index(
        "ix_synthetic_generation_runs_status",
        table_name="synthetic_generation_runs",
    )
    op.drop_index(
        "ix_synthetic_generation_runs_started_at",
        table_name="synthetic_generation_runs",
    )
    op.drop_table("synthetic_generation_runs")
