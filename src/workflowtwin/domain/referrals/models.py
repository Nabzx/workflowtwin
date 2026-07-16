"""Version 1 contracts for referral cases and append-only events."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from workflowtwin.domain.referrals.enums import (
    REASON_CODES_BY_EVENT,
    TERMINAL_STATUSES,
    ActorType,
    CommunicationChannel,
    EventType,
    ReasonCode,
    ReferralSource,
    ReferralStatus,
    ServiceLine,
    SourceSystem,
)

SchemaVersion = Literal[1]
ExternalCaseId = Annotated[
    str,
    StringConstraints(pattern=r"^NSC-REF-[A-Z0-9]{4,32}$", max_length=40),
]
ExternalEventId = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z0-9][A-Z0-9._:-]{5,127}$", max_length=128),
]
ActorIdentifier = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z][A-Z0-9_-]{2,63}$", max_length=64),
]

IDENTIFIED_ACTOR_TYPES = frozenset(
    {ActorType.ADMIN_STAFF, ActorType.CLINICAL_TEAM, ActorType.SCHEDULING_STAFF}
)
FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "address",
        "clinical_notes",
        "clinical_narrative",
        "diagnosis",
        "email",
        "medical_history",
        "nhs_number",
        "patient_name",
        "patient_risk_score",
        "phone_number",
        "treatment",
    }
)


def _as_utc(value: datetime) -> datetime:
    """Require an aware timestamp and normalise it to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _find_forbidden_metadata_key(value: Any) -> str | None:
    """Find prohibited direct-patient or clinical keys in nested metadata."""
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalised_key = str(key).strip().lower().replace("-", "_").replace(" ", "_")
            if normalised_key in FORBIDDEN_METADATA_KEYS:
                return normalised_key
            if forbidden_key := _find_forbidden_metadata_key(nested_value):
                return forbidden_key
    elif isinstance(value, list):
        for item in value:
            if forbidden_key := _find_forbidden_metadata_key(item):
                return forbidden_key
    return None


class DomainModel(BaseModel):
    """Strict immutable snapshot used at the domain boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ReferralCase(DomainModel):
    """One complete instance of the fictional Northstar referral process."""

    id: UUID
    external_source_id: ExternalCaseId
    referral_source: ReferralSource
    service_line: ServiceLine
    status: ReferralStatus
    received_at: datetime
    closed_at: datetime | None = None
    is_synthetic: bool
    schema_version: SchemaVersion = 1
    created_at: datetime
    updated_at: datetime

    @field_validator("received_at", "closed_at", "created_at", "updated_at")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        """Require UTC-capable timestamps throughout the case contract."""
        return None if value is None else _as_utc(value)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        """Keep the current projection consistent without policing event sequence."""
        is_terminal = self.status in TERMINAL_STATUSES
        if is_terminal and self.closed_at is None:
            raise ValueError("a terminal referral status requires closed_at")
        if not is_terminal and self.closed_at is not None:
            raise ValueError("closed_at requires a terminal referral status")
        if self.closed_at is not None and self.closed_at < self.received_at:
            raise ValueError("closed_at cannot be earlier than received_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self


class ReferralEvent(DomainModel):
    """An append-only fact observed during a referral lifecycle."""

    id: UUID
    referral_case_id: UUID
    external_event_id: ExternalEventId
    event_type: EventType
    event_at: datetime
    ingested_at: datetime
    actor_type: ActorType
    actor_identifier: ActorIdentifier | None = None
    source_system: SourceSystem
    channel: CommunicationChannel
    requires_manual_work: bool
    reason_code: ReasonCode | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: SchemaVersion = 1

    @field_validator("event_at", "ingested_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Require UTC-capable event and ingestion timestamps independently."""
        return _as_utc(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Reject metadata fields outside the administrative safety boundary."""
        if forbidden_key := _find_forbidden_metadata_key(value):
            raise ValueError(f"metadata key '{forbidden_key}' is not permitted")
        return value

    @model_validator(mode="after")
    def validate_operational_context(self) -> Self:
        """Require actor identity and compatible reasons where they carry meaning."""
        if self.actor_type in IDENTIFIED_ACTOR_TYPES and self.actor_identifier is None:
            raise ValueError(f"actor_identifier is required for {self.actor_type.value}")

        permitted_reason_codes = REASON_CODES_BY_EVENT.get(self.event_type)
        if permitted_reason_codes is not None:
            if self.reason_code is None:
                raise ValueError(f"reason_code is required for {self.event_type.value}")
            if self.reason_code not in permitted_reason_codes:
                raise ValueError(
                    f"reason_code {self.reason_code.value} is invalid for {self.event_type.value}"
                )
        return self
