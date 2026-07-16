"""SQLAlchemy records for referral cases and append-only events."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship

from workflowtwin.domain.referrals.enums import (
    ActorType,
    CommunicationChannel,
    EventType,
    ReasonCode,
    ReferralSource,
    ReferralStatus,
    ServiceLine,
    SourceSystem,
)
from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent
from workflowtwin.infrastructure.database import Base


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    """Persist public string values rather than Python enum member names."""
    return [member.value for member in enum_class]


def _string_enum(enum_class: type[StrEnum], name: str, length: int) -> Enum:
    """Build a portable constrained string enum with explicit migration names."""
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=_enum_values,
        length=length,
    )


class ReferralCaseRecord(Base):
    """Queryable current projection of a referral process instance."""

    __tablename__ = "referral_cases"
    __table_args__ = (
        CheckConstraint("schema_version = 1", name="supported_schema_version"),
        CheckConstraint(
            "external_source_id ~ '^NSC-REF-[A-Z0-9]{4,32}$'",
            name="external_source_id_format",
        ),
        CheckConstraint(
            "(closed_at IS NULL AND status NOT IN "
            "('completed', 'cancelled', 'rejected', 'closed_other')) OR "
            "(closed_at IS NOT NULL AND status IN "
            "('completed', 'cancelled', 'rejected', 'closed_other'))",
            name="terminal_status_matches_closed_at",
        ),
        CheckConstraint(
            "closed_at IS NULL OR closed_at >= received_at",
            name="closed_at_after_received_at",
        ),
        Index("ix_referral_cases_status", "status"),
        Index("ix_referral_cases_received_at", "received_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    external_source_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    referral_source: Mapped[ReferralSource] = mapped_column(
        _string_enum(ReferralSource, "referral_source", 32), nullable=False
    )
    service_line: Mapped[ServiceLine] = mapped_column(
        _string_enum(ServiceLine, "service_line", 32), nullable=False
    )
    status: Mapped[ReferralStatus] = mapped_column(
        _string_enum(ReferralStatus, "referral_status", 32), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list["ReferralEventRecord"]] = relationship(
        back_populates="referral_case",
        order_by="ReferralEventRecord.event_at",
        passive_deletes=True,
    )

    @classmethod
    def from_domain(cls, referral_case: ReferralCase) -> Self:
        """Create a persistence record from a validated domain snapshot."""
        return cls(
            id=referral_case.id,
            external_source_id=referral_case.external_source_id,
            referral_source=referral_case.referral_source,
            service_line=referral_case.service_line,
            status=referral_case.status,
            received_at=referral_case.received_at,
            closed_at=referral_case.closed_at,
            is_synthetic=referral_case.is_synthetic,
            schema_version=referral_case.schema_version,
            created_at=referral_case.created_at,
            updated_at=referral_case.updated_at,
        )


class ReferralEventRecord(Base):
    """Append-only recorded fact in a referral lifecycle."""

    __tablename__ = "referral_events"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "external_event_id",
            name="uq_referral_events_source_external_event",
        ),
        CheckConstraint("schema_version = 1", name="supported_schema_version"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_is_object"),
        CheckConstraint(
            "event_type NOT IN ("
            "'missing_information_requested', 'referral_recategorised', "
            "'clinical_team_reassigned', 'appointment_scheduling_failed', "
            "'patient_no_response', 'referral_cancelled', 'referral_rejected', "
            "'referral_closed_other') OR reason_code IS NOT NULL",
            name="reason_required_for_exception_event",
        ),
        Index("ix_referral_events_case_event_at", "referral_case_id", "event_at"),
        Index("ix_referral_events_event_type", "event_type"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    referral_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("referral_cases.id", ondelete="RESTRICT"), nullable=False
    )
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[EventType] = mapped_column(
        _string_enum(EventType, "referral_event_type", 48), nullable=False
    )
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_type: Mapped[ActorType] = mapped_column(
        _string_enum(ActorType, "referral_actor_type", 32), nullable=False
    )
    actor_identifier: Mapped[str | None] = mapped_column(String(64))
    source_system: Mapped[SourceSystem] = mapped_column(
        _string_enum(SourceSystem, "referral_source_system", 32), nullable=False
    )
    channel: Mapped[CommunicationChannel] = mapped_column(
        _string_enum(CommunicationChannel, "referral_communication_channel", 32),
        nullable=False,
    )
    requires_manual_work: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_code: Mapped[ReasonCode | None] = mapped_column(
        _string_enum(ReasonCode, "referral_reason_code", 40)
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
    schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    referral_case: Mapped[ReferralCaseRecord] = relationship(back_populates="events")

    @classmethod
    def from_domain(cls, referral_event: ReferralEvent) -> Self:
        """Create a persistence record from a validated append-only fact."""
        return cls(
            id=referral_event.id,
            referral_case_id=referral_event.referral_case_id,
            external_event_id=referral_event.external_event_id,
            event_type=referral_event.event_type,
            event_at=referral_event.event_at,
            ingested_at=referral_event.ingested_at,
            actor_type=referral_event.actor_type,
            actor_identifier=referral_event.actor_identifier,
            source_system=referral_event.source_system,
            channel=referral_event.channel,
            requires_manual_work=referral_event.requires_manual_work,
            reason_code=referral_event.reason_code,
            event_metadata=referral_event.metadata,
            schema_version=referral_event.schema_version,
        )


class ImmutableEventError(RuntimeError):
    """Raised when application code attempts to rewrite an event fact."""


@event.listens_for(ReferralEventRecord, "before_update", propagate=True)
def _reject_event_update(
    _mapper: Mapper[ReferralEventRecord],
    _connection: Connection,
    _target: ReferralEventRecord,
) -> None:
    raise ImmutableEventError("referral events are append-only and cannot be updated")


@event.listens_for(ReferralEventRecord, "before_delete", propagate=True)
def _reject_event_delete(
    _mapper: Mapper[ReferralEventRecord],
    _connection: Connection,
    _target: ReferralEventRecord,
) -> None:
    raise ImmutableEventError("referral events are append-only and cannot be deleted")
