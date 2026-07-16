"""Validation tests for version 1 referral contracts."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from workflowtwin.domain.referrals.enums import (
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
from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent

CASE_ID = UUID("00000000-0000-5000-8000-000000000001")
EVENT_ID = UUID("00000000-0000-5000-8000-000000000101")
NOW = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


def case_data(**overrides: object) -> dict[str, object]:
    """Return the smallest valid fictional case payload."""
    data: dict[str, object] = {
        "id": CASE_ID,
        "external_source_id": "NSC-REF-TEST0001",
        "referral_source": ReferralSource.GP_PRACTICE,
        "service_line": ServiceLine.MUSCULOSKELETAL,
        "status": ReferralStatus.RECEIVED,
        "received_at": NOW,
        "closed_at": None,
        "is_synthetic": True,
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    data.update(overrides)
    return data


def event_data(**overrides: object) -> dict[str, object]:
    """Return the smallest valid fictional event payload."""
    data: dict[str, object] = {
        "id": EVENT_ID,
        "referral_case_id": CASE_ID,
        "external_event_id": "SYNTH:TEST0001:001",
        "event_type": EventType.REFERRAL_RECEIVED,
        "event_at": NOW,
        "ingested_at": NOW + timedelta(minutes=1),
        "actor_type": ActorType.SYSTEM,
        "source_system": SourceSystem.SYNTHETIC_GENERATOR,
        "channel": CommunicationChannel.INTERNAL_SYSTEM,
        "requires_manual_work": False,
        "schema_version": 1,
    }
    data.update(overrides)
    return data


def test_operational_vocabularies_are_stable_string_values() -> None:
    assert ReferralStatus.AWAITING_INFORMATION.value == "awaiting_information"
    assert EventType.REFERRAL_RECATEGORISED.value == "referral_recategorised"
    assert ReasonCode.NO_APPOINTMENT_SLOT.value == "no_appointment_slot"
    assert {
        ReferralStatus.COMPLETED,
        ReferralStatus.CANCELLED,
        ReferralStatus.REJECTED,
        ReferralStatus.CLOSED_OTHER,
    } == TERMINAL_STATUSES


@pytest.mark.parametrize("status", TERMINAL_STATUSES)
def test_terminal_case_requires_closed_at(status: ReferralStatus) -> None:
    with pytest.raises(ValidationError, match="requires closed_at"):
        ReferralCase.model_validate(case_data(status=status))


def test_open_case_cannot_have_closed_at() -> None:
    with pytest.raises(ValidationError, match="requires a terminal"):
        ReferralCase.model_validate(case_data(closed_at=NOW + timedelta(days=1)))


def test_case_closure_cannot_precede_receipt() -> None:
    with pytest.raises(ValidationError, match="cannot be earlier"):
        ReferralCase.model_validate(
            case_data(
                status=ReferralStatus.CANCELLED,
                closed_at=NOW - timedelta(minutes=1),
            )
        )


def test_case_requires_supported_schema_and_external_id() -> None:
    with pytest.raises(ValidationError):
        ReferralCase.model_validate(case_data(schema_version=2))
    with pytest.raises(ValidationError):
        ReferralCase.model_validate(case_data(external_source_id="real-patient-id"))


def test_timestamps_must_be_aware_and_are_normalised_to_utc() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        ReferralEvent.model_validate(event_data(event_at=NOW.replace(tzinfo=None)))

    event = ReferralEvent.model_validate(
        event_data(event_at=datetime(2026, 1, 5, 10, 0, tzinfo=timezone(timedelta(hours=1))))
    )
    assert event.event_at == NOW
    assert event.event_at.tzinfo is UTC


def test_event_accepts_delayed_and_out_of_order_source_time() -> None:
    event = ReferralEvent.model_validate(
        event_data(event_at=NOW - timedelta(days=2), ingested_at=NOW + timedelta(days=3))
    )
    assert event.event_at < event.ingested_at


@pytest.mark.parametrize(
    ("event_type", "reason_code"),
    [
        (EventType.MISSING_INFORMATION_REQUESTED, None),
        (EventType.APPOINTMENT_SCHEDULING_FAILED, None),
        (EventType.REFERRAL_CANCELLED, None),
        (EventType.REFERRAL_REJECTED, ReasonCode.PATIENT_CANCELLED),
    ],
)
def test_reason_codes_are_required_and_event_specific(
    event_type: EventType, reason_code: ReasonCode | None
) -> None:
    with pytest.raises(ValidationError, match="reason_code"):
        ReferralEvent.model_validate(event_data(event_type=event_type, reason_code=reason_code))


def test_operational_actor_requires_identifier() -> None:
    with pytest.raises(ValidationError, match="actor_identifier"):
        ReferralEvent.model_validate(event_data(actor_type=ActorType.ADMIN_STAFF))


@pytest.mark.parametrize(
    "metadata",
    [
        {"patient_name": "Fictional Person"},
        {"source": {"nhs-number": "not-allowed"}},
        {"items": [{"clinical notes": "not-allowed"}]},
    ],
)
def test_metadata_rejects_direct_patient_and_clinical_fields(metadata: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="not permitted"):
        ReferralEvent.model_validate(event_data(metadata=metadata))


def test_event_contract_is_frozen() -> None:
    event = ReferralEvent.model_validate(event_data())

    with pytest.raises(ValidationError, match="frozen"):
        event.__setattr__("event_type", EventType.REFERRAL_COMPLETED)
