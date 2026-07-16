"""Create referral case and append-only event tables.

Revision ID: 20260716_0001
Revises:
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REFERRAL_SOURCES = (
    "gp_practice",
    "community_clinic",
    "healthcare_professional",
    "internal_transfer",
)
SERVICE_LINES = ("cardiology", "dermatology", "musculoskeletal", "neurology", "respiratory")
REFERRAL_STATUSES = (
    "received",
    "awaiting_information",
    "ready_for_categorisation",
    "categorised",
    "assigned",
    "scheduling",
    "appointment_booked",
    "completed",
    "cancelled",
    "rejected",
    "closed_other",
)
EVENT_TYPES = (
    "referral_submitted",
    "referral_received",
    "completeness_check_completed",
    "missing_information_requested",
    "missing_information_received",
    "referral_categorised",
    "referral_recategorised",
    "clinical_team_assigned",
    "clinical_team_reassigned",
    "appointment_scheduling_started",
    "appointment_scheduling_failed",
    "appointment_booked",
    "patient_notified",
    "patient_no_response",
    "referral_completed",
    "referral_cancelled",
    "referral_rejected",
    "referral_closed_other",
)
ACTOR_TYPES = (
    "referrer",
    "admin_staff",
    "clinical_team",
    "scheduling_staff",
    "patient",
    "system",
)
SOURCE_SYSTEMS = (
    "referral_portal",
    "secure_email",
    "admin_system",
    "scheduling_system",
    "manual_entry",
    "synthetic_generator",
)
CHANNELS = (
    "portal",
    "secure_email",
    "phone",
    "sms",
    "letter",
    "internal_system",
    "not_applicable",
)
REASON_CODES = (
    "missing_administrative_details",
    "invalid_administrative_details",
    "incorrect_category",
    "routing_correction",
    "capacity_rebalance",
    "no_appointment_slot",
    "scheduling_system_error",
    "patient_unavailable",
    "patient_unreachable",
    "referrer_withdrew",
    "patient_cancelled",
    "duplicate_referral",
    "out_of_scope_service",
    "invalid_referral_source",
    "other_operational",
)


def _allowed(column: str, values: tuple[str, ...]) -> str:
    """Build a reviewed SQL check expression from migration constants."""
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    """Create referral persistence and database-level immutability controls."""
    op.create_table(
        "referral_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_source_id", sa.String(length=40), nullable=False),
        sa.Column("referral_source", sa.String(length=32), nullable=False),
        sa.Column("service_line", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(_allowed("referral_source", REFERRAL_SOURCES), name="referral_source"),
        sa.CheckConstraint(_allowed("service_line", SERVICE_LINES), name="service_line"),
        sa.CheckConstraint(_allowed("status", REFERRAL_STATUSES), name="referral_status"),
        sa.CheckConstraint("schema_version = 1", name="supported_schema_version"),
        sa.CheckConstraint(
            "external_source_id ~ '^NSC-REF-[A-Z0-9]{4,32}$'",
            name="external_source_id_format",
        ),
        sa.CheckConstraint(
            "(closed_at IS NULL AND status NOT IN "
            "('completed', 'cancelled', 'rejected', 'closed_other')) OR "
            "(closed_at IS NOT NULL AND status IN "
            "('completed', 'cancelled', 'rejected', 'closed_other'))",
            name="terminal_status_matches_closed_at",
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR closed_at >= received_at",
            name="closed_at_after_received_at",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_source_id"),
    )
    op.create_index("ix_referral_cases_received_at", "referral_cases", ["received_at"])
    op.create_index("ix_referral_cases_status", "referral_cases", ["status"])

    op.create_table(
        "referral_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("referral_case_id", sa.Uuid(), nullable=False),
        sa.Column("external_event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_identifier", sa.String(length=64), nullable=True),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("requires_manual_work", sa.Boolean(), nullable=False),
        sa.Column("reason_code", sa.String(length=40), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(_allowed("event_type", EVENT_TYPES), name="referral_event_type"),
        sa.CheckConstraint(_allowed("actor_type", ACTOR_TYPES), name="referral_actor_type"),
        sa.CheckConstraint(
            _allowed("source_system", SOURCE_SYSTEMS), name="referral_source_system"
        ),
        sa.CheckConstraint(_allowed("channel", CHANNELS), name="referral_communication_channel"),
        sa.CheckConstraint(
            f"reason_code IS NULL OR {_allowed('reason_code', REASON_CODES)}",
            name="referral_reason_code",
        ),
        sa.CheckConstraint("schema_version = 1", name="supported_schema_version"),
        sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_is_object"),
        sa.CheckConstraint(
            "event_type NOT IN ("
            "'missing_information_requested', 'referral_recategorised', "
            "'clinical_team_reassigned', 'appointment_scheduling_failed', "
            "'patient_no_response', 'referral_cancelled', 'referral_rejected', "
            "'referral_closed_other') OR reason_code IS NOT NULL",
            name="reason_required_for_exception_event",
        ),
        sa.ForeignKeyConstraint(["referral_case_id"], ["referral_cases.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "external_event_id",
            name="uq_referral_events_source_external_event",
        ),
    )
    op.create_index(
        "ix_referral_events_case_event_at",
        "referral_events",
        ["referral_case_id", "event_at"],
    )
    op.create_index("ix_referral_events_event_type", "referral_events", ["event_type"])

    op.execute(
        """
        CREATE FUNCTION workflowtwin_reject_referral_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'referral events are append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER referral_events_are_append_only
        BEFORE UPDATE OR DELETE ON referral_events
        FOR EACH ROW
        EXECUTE FUNCTION workflowtwin_reject_referral_event_mutation()
        """
    )


def downgrade() -> None:
    """Remove referral persistence and its immutability controls."""
    op.execute("DROP TRIGGER referral_events_are_append_only ON referral_events")
    op.execute("DROP FUNCTION workflowtwin_reject_referral_event_mutation()")
    op.drop_index("ix_referral_events_event_type", table_name="referral_events")
    op.drop_index("ix_referral_events_case_event_at", table_name="referral_events")
    op.drop_table("referral_events")
    op.drop_index("ix_referral_cases_status", table_name="referral_cases")
    op.drop_index("ix_referral_cases_received_at", table_name="referral_cases")
    op.drop_table("referral_cases")
