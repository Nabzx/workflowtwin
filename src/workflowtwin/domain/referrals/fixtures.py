"""Deterministic fictional referral scenarios for tests and local development."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

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

FIXTURE_NAMESPACE = UUID("7db4480c-51b4-4baa-b2b3-9fb8f22089ab")
BASE_TIME = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class ScenarioExpectation:
    """Known properties for future analytical assertions."""

    terminal_status: ReferralStatus | None
    missing_information_requests: int = 0
    rework_events: int = 0
    scheduling_failures: int = 0
    contains_duplicate_source_event: bool = False
    contains_out_of_order_ingestion: bool = False
    expected_stuck: bool = False


@dataclass(frozen=True, slots=True)
class ReferralScenario:
    """A fictional case, its ingestion-ordered events, and expected properties."""

    name: str
    case: ReferralCase
    events: tuple[ReferralEvent, ...]
    expectation: ScenarioExpectation


@dataclass(frozen=True, slots=True)
class _EventStep:
    event_type: EventType
    hours_after_receipt: float
    actor_type: ActorType = ActorType.SYSTEM
    actor_identifier: str | None = None
    channel: CommunicationChannel = CommunicationChannel.INTERNAL_SYSTEM
    manual: bool = False
    reason_code: ReasonCode | None = None
    ingestion_delay_hours: float = 0.02
    external_event_id: str | None = None


def _step(
    event_type: EventType,
    hours: float,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_identifier: str | None = None,
    *,
    channel: CommunicationChannel = CommunicationChannel.INTERNAL_SYSTEM,
    manual: bool = False,
    reason_code: ReasonCode | None = None,
    ingestion_delay_hours: float = 0.02,
    external_event_id: str | None = None,
) -> _EventStep:
    return _EventStep(
        event_type=event_type,
        hours_after_receipt=hours,
        actor_type=actor_type,
        actor_identifier=actor_identifier,
        channel=channel,
        manual=manual,
        reason_code=reason_code,
        ingestion_delay_hours=ingestion_delay_hours,
        external_event_id=external_event_id,
    )


def _opening_steps() -> list[_EventStep]:
    return [
        _step(
            EventType.REFERRAL_SUBMITTED,
            -1,
            ActorType.REFERRER,
            channel=CommunicationChannel.PORTAL,
        ),
        _step(EventType.REFERRAL_RECEIVED, 0),
    ]


def _successful_tail(start: float) -> list[_EventStep]:
    return [
        _step(
            EventType.REFERRAL_CATEGORISED,
            start,
            ActorType.ADMIN_STAFF,
            "ADMIN-001",
            manual=True,
        ),
        _step(
            EventType.CLINICAL_TEAM_ASSIGNED,
            start + 1,
            ActorType.ADMIN_STAFF,
            "ADMIN-001",
            manual=True,
        ),
        _step(
            EventType.APPOINTMENT_SCHEDULING_STARTED,
            start + 2,
            ActorType.SCHEDULING_STAFF,
            "SCHED-001",
            manual=True,
        ),
        _step(
            EventType.APPOINTMENT_BOOKED,
            start + 4,
            ActorType.SCHEDULING_STAFF,
            "SCHED-001",
            manual=True,
        ),
        _step(
            EventType.PATIENT_NOTIFIED,
            start + 4.1,
            channel=CommunicationChannel.SMS,
        ),
        _step(
            EventType.REFERRAL_COMPLETED,
            start + 5,
            ActorType.ADMIN_STAFF,
            "ADMIN-001",
            manual=True,
        ),
    ]


def _build_scenario(
    *,
    name: str,
    code: str,
    day_offset: int,
    status: ReferralStatus,
    steps: list[_EventStep],
    expectation: ScenarioExpectation,
    service_line: ServiceLine = ServiceLine.MUSCULOSKELETAL,
) -> ReferralScenario:
    received_at = BASE_TIME + timedelta(days=day_offset)
    case_id = uuid5(FIXTURE_NAMESPACE, f"{code}:case")
    events = []

    for index, step in enumerate(steps, start=1):
        event_at = received_at + timedelta(hours=step.hours_after_receipt)
        external_event_id = step.external_event_id or f"SYNTH:{code}:{index:03}"
        events.append(
            ReferralEvent(
                id=uuid5(FIXTURE_NAMESPACE, f"{code}:event:{index}"),
                referral_case_id=case_id,
                external_event_id=external_event_id,
                event_type=step.event_type,
                event_at=event_at,
                ingested_at=event_at + timedelta(hours=step.ingestion_delay_hours),
                actor_type=step.actor_type,
                actor_identifier=step.actor_identifier,
                source_system=SourceSystem.SYNTHETIC_GENERATOR,
                channel=step.channel,
                requires_manual_work=step.manual,
                reason_code=step.reason_code,
                metadata={"fixture_scenario": name},
                schema_version=1,
            )
        )

    events.sort(key=lambda event: (event.ingested_at, event.id.hex))
    terminal_event_types = {
        EventType.REFERRAL_COMPLETED,
        EventType.REFERRAL_CANCELLED,
        EventType.REFERRAL_REJECTED,
        EventType.REFERRAL_CLOSED_OTHER,
    }
    closed_at = next(
        (event.event_at for event in events if event.event_type in terminal_event_types), None
    )
    latest_ingestion = max(event.ingested_at for event in events)
    referral_case = ReferralCase(
        id=case_id,
        external_source_id=f"NSC-REF-{code}",
        referral_source=ReferralSource.GP_PRACTICE,
        service_line=service_line,
        status=status,
        received_at=received_at,
        closed_at=closed_at,
        is_synthetic=True,
        schema_version=1,
        created_at=received_at,
        updated_at=latest_ingestion,
    )
    return ReferralScenario(name, referral_case, tuple(events), expectation)


def straight_through_successful_referral() -> ReferralScenario:
    """A complete referral with no exception or repeated work."""
    steps = [
        *_opening_steps(),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-001",
            manual=True,
        ),
        *_successful_tail(3),
    ]
    return _build_scenario(
        name="straight_through_successful_referral",
        code="STRAIGHT0001",
        day_offset=0,
        status=ReferralStatus.COMPLETED,
        steps=steps,
        expectation=ScenarioExpectation(terminal_status=ReferralStatus.COMPLETED),
    )


def referral_missing_information_once() -> ReferralScenario:
    """One missing-information wait followed by a successful referral."""
    steps = [
        *_opening_steps(),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-002",
            manual=True,
        ),
        _step(
            EventType.MISSING_INFORMATION_REQUESTED,
            2.5,
            ActorType.ADMIN_STAFF,
            "ADMIN-002",
            channel=CommunicationChannel.SECURE_EMAIL,
            manual=True,
            reason_code=ReasonCode.MISSING_ADMINISTRATIVE_DETAILS,
        ),
        _step(
            EventType.MISSING_INFORMATION_RECEIVED,
            26,
            ActorType.REFERRER,
            channel=CommunicationChannel.SECURE_EMAIL,
        ),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            27,
            ActorType.ADMIN_STAFF,
            "ADMIN-002",
            manual=True,
        ),
        *_successful_tail(28),
    ]
    return _build_scenario(
        name="referral_missing_information_once",
        code="MISSING0001",
        day_offset=1,
        status=ReferralStatus.COMPLETED,
        steps=steps,
        expectation=ScenarioExpectation(
            terminal_status=ReferralStatus.COMPLETED,
            missing_information_requests=1,
            rework_events=1,
        ),
    )


def referral_with_repeated_missing_information_requests() -> ReferralScenario:
    """Two information loops and three completeness checks."""
    steps = [
        *_opening_steps(),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-003",
            manual=True,
        ),
        _step(
            EventType.MISSING_INFORMATION_REQUESTED,
            3,
            ActorType.ADMIN_STAFF,
            "ADMIN-003",
            manual=True,
            reason_code=ReasonCode.MISSING_ADMINISTRATIVE_DETAILS,
        ),
        _step(EventType.MISSING_INFORMATION_RECEIVED, 27, ActorType.REFERRER),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            28,
            ActorType.ADMIN_STAFF,
            "ADMIN-003",
            manual=True,
        ),
        _step(
            EventType.MISSING_INFORMATION_REQUESTED,
            29,
            ActorType.ADMIN_STAFF,
            "ADMIN-003",
            manual=True,
            reason_code=ReasonCode.INVALID_ADMINISTRATIVE_DETAILS,
        ),
        _step(EventType.MISSING_INFORMATION_RECEIVED, 53, ActorType.REFERRER),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            54,
            ActorType.ADMIN_STAFF,
            "ADMIN-003",
            manual=True,
        ),
        *_successful_tail(55),
    ]
    return _build_scenario(
        name="referral_with_repeated_missing_information_requests",
        code="MISSING0002",
        day_offset=2,
        status=ReferralStatus.COMPLETED,
        steps=steps,
        expectation=ScenarioExpectation(
            terminal_status=ReferralStatus.COMPLETED,
            missing_information_requests=2,
            rework_events=3,
        ),
    )


def referral_recategorised_and_reassigned() -> ReferralScenario:
    """A routing correction followed by a capacity-driven team handoff."""
    steps = [
        *_opening_steps(),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-004",
            manual=True,
        ),
        _step(
            EventType.REFERRAL_CATEGORISED,
            3,
            ActorType.ADMIN_STAFF,
            "ADMIN-004",
            manual=True,
        ),
        _step(
            EventType.REFERRAL_RECATEGORISED,
            5,
            ActorType.ADMIN_STAFF,
            "ADMIN-005",
            manual=True,
            reason_code=ReasonCode.INCORRECT_CATEGORY,
        ),
        _step(
            EventType.CLINICAL_TEAM_ASSIGNED,
            6,
            ActorType.ADMIN_STAFF,
            "ADMIN-005",
            manual=True,
        ),
        _step(
            EventType.CLINICAL_TEAM_REASSIGNED,
            10,
            ActorType.CLINICAL_TEAM,
            "TEAM-MSK",
            manual=True,
            reason_code=ReasonCode.CAPACITY_REBALANCE,
        ),
        *_successful_tail(11)[2:],
    ]
    return _build_scenario(
        name="referral_recategorised_and_reassigned",
        code="REROUTE0001",
        day_offset=3,
        status=ReferralStatus.COMPLETED,
        steps=steps,
        expectation=ScenarioExpectation(terminal_status=ReferralStatus.COMPLETED, rework_events=2),
        service_line=ServiceLine.DERMATOLOGY,
    )


def referral_with_failed_scheduling_attempts() -> ReferralScenario:
    """Two failed attempts before an appointment is booked."""
    steps = [
        *_opening_steps(),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-006",
            manual=True,
        ),
        *_successful_tail(3)[:2],
        _step(
            EventType.APPOINTMENT_SCHEDULING_STARTED,
            5,
            ActorType.SCHEDULING_STAFF,
            "SCHED-002",
            manual=True,
        ),
        _step(
            EventType.APPOINTMENT_SCHEDULING_FAILED,
            6,
            ActorType.SCHEDULING_STAFF,
            "SCHED-002",
            manual=True,
            reason_code=ReasonCode.NO_APPOINTMENT_SLOT,
        ),
        _step(
            EventType.APPOINTMENT_SCHEDULING_STARTED,
            30,
            ActorType.SCHEDULING_STAFF,
            "SCHED-002",
            manual=True,
        ),
        _step(
            EventType.APPOINTMENT_SCHEDULING_FAILED,
            31,
            ActorType.SCHEDULING_STAFF,
            "SCHED-002",
            manual=True,
            reason_code=ReasonCode.PATIENT_UNAVAILABLE,
        ),
        _step(
            EventType.APPOINTMENT_SCHEDULING_STARTED,
            55,
            ActorType.SCHEDULING_STAFF,
            "SCHED-002",
            manual=True,
        ),
        *_successful_tail(55)[3:],
    ]
    return _build_scenario(
        name="referral_with_failed_scheduling_attempts",
        code="SCHEDULE0001",
        day_offset=4,
        status=ReferralStatus.COMPLETED,
        steps=steps,
        expectation=ScenarioExpectation(
            terminal_status=ReferralStatus.COMPLETED,
            rework_events=2,
            scheduling_failures=2,
        ),
    )


def cancelled_referral() -> ReferralScenario:
    """A referral cancelled while waiting for administrative information."""
    steps = [
        *_opening_steps(),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-007",
            manual=True,
        ),
        _step(
            EventType.MISSING_INFORMATION_REQUESTED,
            3,
            ActorType.ADMIN_STAFF,
            "ADMIN-007",
            manual=True,
            reason_code=ReasonCode.MISSING_ADMINISTRATIVE_DETAILS,
        ),
        _step(
            EventType.REFERRAL_CANCELLED,
            51,
            ActorType.ADMIN_STAFF,
            "ADMIN-007",
            manual=True,
            reason_code=ReasonCode.REFERRER_WITHDREW,
        ),
    ]
    return _build_scenario(
        name="cancelled_referral",
        code="CANCEL0001",
        day_offset=5,
        status=ReferralStatus.CANCELLED,
        steps=steps,
        expectation=ScenarioExpectation(
            terminal_status=ReferralStatus.CANCELLED, missing_information_requests=1
        ),
    )


def rejected_referral() -> ReferralScenario:
    """A referral rejected for an administrative scope mismatch."""
    steps = [
        *_opening_steps(),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-008",
            manual=True,
        ),
        _step(
            EventType.REFERRAL_REJECTED,
            3,
            ActorType.ADMIN_STAFF,
            "ADMIN-008",
            manual=True,
            reason_code=ReasonCode.OUT_OF_SCOPE_SERVICE,
        ),
    ]
    return _build_scenario(
        name="rejected_referral",
        code="REJECT0001",
        day_offset=6,
        status=ReferralStatus.REJECTED,
        steps=steps,
        expectation=ScenarioExpectation(terminal_status=ReferralStatus.REJECTED),
    )


def stuck_referral() -> ReferralScenario:
    """An open referral with no progress after patient non-response."""
    steps = [
        *_opening_steps(),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-009",
            manual=True,
        ),
        _step(
            EventType.MISSING_INFORMATION_REQUESTED,
            3,
            ActorType.ADMIN_STAFF,
            "ADMIN-009",
            manual=True,
            reason_code=ReasonCode.MISSING_ADMINISTRATIVE_DETAILS,
        ),
        _step(
            EventType.PATIENT_NO_RESPONSE,
            171,
            ActorType.ADMIN_STAFF,
            "ADMIN-009",
            manual=True,
            reason_code=ReasonCode.PATIENT_UNREACHABLE,
        ),
    ]
    return _build_scenario(
        name="stuck_referral",
        code="STUCK0001",
        day_offset=7,
        status=ReferralStatus.AWAITING_INFORMATION,
        steps=steps,
        expectation=ScenarioExpectation(
            terminal_status=None,
            missing_information_requests=1,
            expected_stuck=True,
        ),
    )


def referral_with_duplicate_source_event() -> ReferralScenario:
    """Two distinct event records carrying one source-system identity."""
    duplicate_id = "SYNTH:DUPLICATE0001:002"
    steps = [
        _step(EventType.REFERRAL_SUBMITTED, -1, ActorType.REFERRER),
        _step(EventType.REFERRAL_RECEIVED, 0, external_event_id=duplicate_id),
        _step(
            EventType.REFERRAL_RECEIVED,
            0,
            ingestion_delay_hours=0.5,
            external_event_id=duplicate_id,
        ),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-010",
            manual=True,
        ),
        *_successful_tail(3),
    ]
    return _build_scenario(
        name="referral_with_duplicate_source_event",
        code="DUPLICATE0001",
        day_offset=8,
        status=ReferralStatus.COMPLETED,
        steps=steps,
        expectation=ScenarioExpectation(
            terminal_status=ReferralStatus.COMPLETED,
            contains_duplicate_source_event=True,
        ),
    )


def referral_with_delayed_out_of_order_ingestion() -> ReferralScenario:
    """A completeness check ingested after a later categorisation fact."""
    steps = [
        *_opening_steps(),
        _step(
            EventType.COMPLETENESS_CHECK_COMPLETED,
            2,
            ActorType.ADMIN_STAFF,
            "ADMIN-011",
            manual=True,
            ingestion_delay_hours=8,
        ),
        _step(
            EventType.REFERRAL_CATEGORISED,
            4,
            ActorType.ADMIN_STAFF,
            "ADMIN-011",
            manual=True,
        ),
        *_successful_tail(11)[1:],
    ]
    return _build_scenario(
        name="referral_with_delayed_out_of_order_ingestion",
        code="DELAYED0001",
        day_offset=9,
        status=ReferralStatus.COMPLETED,
        steps=steps,
        expectation=ScenarioExpectation(
            terminal_status=ReferralStatus.COMPLETED,
            contains_out_of_order_ingestion=True,
        ),
    )


def all_referral_scenarios() -> tuple[ReferralScenario, ...]:
    """Return every deterministic version 1 fixture in a stable order."""
    return (
        straight_through_successful_referral(),
        referral_missing_information_once(),
        referral_with_repeated_missing_information_requests(),
        referral_recategorised_and_reassigned(),
        referral_with_failed_scheduling_attempts(),
        cancelled_referral(),
        rejected_referral(),
        stuck_referral(),
        referral_with_duplicate_source_event(),
        referral_with_delayed_out_of_order_ingestion(),
    )
