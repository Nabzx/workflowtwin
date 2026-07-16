"""Seeded coherent case-history generator for fictional Northstar referrals."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from random import Random
from uuid import UUID, uuid5

from workflowtwin.domain.referrals.enums import (
    ActorType,
    CommunicationChannel,
    EventType,
    ReasonCode,
    ReferralStatus,
    SourceSystem,
)
from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent
from workflowtwin.synthetic.config import GenerationConfig
from workflowtwin.synthetic.manifest import build_manifest
from workflowtwin.synthetic.models import (
    BottleneckLabel,
    CaseGroundTruth,
    DefectType,
    DuplicateSourceAttempt,
    EventGroundTruth,
    GeneratedDataset,
    GenerationGroundTruth,
)
from workflowtwin.synthetic.timing import BusinessCalendar

GENERATION_NAMESPACE = UUID("271e2c6e-ad95-44cd-9bc3-4f9f80e1982f")


def _weighted_choice[T](rng: Random, weights: Mapping[T, float]) -> T:
    values = list(weights)
    return rng.choices(values, weights=[weights[value] for value in values], k=1)[0]


def _probability(rng: Random, rate: float) -> bool:
    return rng.random() < min(max(rate, 0.0), 1.0)


class _CaseBuilder:
    """Build one event-time-coherent case using stable identities."""

    def __init__(
        self,
        *,
        run_id: str,
        case_index: int,
        case_id: UUID,
        source_system: SourceSystem,
    ) -> None:
        self.run_id = run_id
        self.run_token = hashlib.sha256(run_id.encode()).hexdigest()[:8].upper()
        self.case_index = case_index
        self.case_id = case_id
        self.source_system = source_system
        self.events: list[ReferralEvent] = []

    def add(
        self,
        *,
        event_type: EventType,
        event_at: datetime,
        actor_type: ActorType,
        actor_identifier: str | None = None,
        source_system: SourceSystem | None = None,
        channel: CommunicationChannel = CommunicationChannel.INTERNAL_SYSTEM,
        manual: bool = False,
        reason_code: ReasonCode | None = None,
        ingestion_delay_minutes: float = 5,
    ) -> ReferralEvent:
        event_index = len(self.events) + 1
        event_id = uuid5(
            GENERATION_NAMESPACE, f"{self.run_id}:case:{self.case_index}:event:{event_index}"
        )
        event = ReferralEvent(
            id=event_id,
            referral_case_id=self.case_id,
            external_event_id=(f"NSTAR:{self.run_token}:{self.case_index:06}:{event_index:03}"),
            event_type=event_type,
            event_at=event_at,
            ingested_at=event_at + timedelta(minutes=ingestion_delay_minutes),
            actor_type=actor_type,
            actor_identifier=actor_identifier,
            source_system=source_system or self.source_system,
            channel=channel,
            requires_manual_work=manual,
            reason_code=reason_code,
            metadata={"generation_run_id": self.run_id},
            schema_version=1,
        )
        self.events.append(event)
        return event


class SyntheticReferralGenerator:
    """Generate deterministic operational contracts and separate evaluation labels."""

    def __init__(self, config: GenerationConfig, *, generated_at: datetime | None = None) -> None:
        self.config = config
        self._generated_at = generated_at or datetime.now(UTC)

    def generate(self) -> GeneratedDataset:
        rng = Random(self.config.seed)
        calendar = BusinessCalendar(self.config)
        run_id = self._resolve_run_id()
        cases: list[ReferralCase] = []
        events: list[ReferralEvent] = []
        case_truth: list[CaseGroundTruth] = []
        event_truth: list[EventGroundTruth] = []
        duplicate_attempts: list[DuplicateSourceAttempt] = []

        for case_index in range(1, self.config.case_count + 1):
            generated = self._generate_case(rng, calendar, run_id, case_index)
            case, case_events, truth, truth_events, attempts = generated
            cases.append(case)
            events.extend(case_events)
            case_truth.append(truth)
            event_truth.extend(truth_events)
            duplicate_attempts.extend(attempts)

        ordered_cases = tuple(sorted(cases, key=lambda case: (case.received_at, case.id.hex)))
        ordered_events = tuple(
            sorted(
                events, key=lambda event: (event.referral_case_id.hex, event.event_at, event.id.hex)
            )
        )
        ground_truth = GenerationGroundTruth(
            run_id=run_id,
            cases=tuple(sorted(case_truth, key=lambda item: item.case_id.hex)),
            events=tuple(sorted(event_truth, key=lambda item: item.event_id.hex)),
            duplicate_attempts=tuple(
                sorted(duplicate_attempts, key=lambda item: item.attempted_event_id.hex)
            ),
        )
        manifest = build_manifest(
            config=self.config,
            run_id=run_id,
            cases=ordered_cases,
            events=ordered_events,
            ground_truth=ground_truth,
            generated_at=self._generated_at,
        )
        return GeneratedDataset(self.config, ordered_cases, ordered_events, ground_truth, manifest)

    def _resolve_run_id(self) -> str:
        if self.config.generation_run_id is not None:
            return self.config.generation_run_id
        config_json = json.dumps(
            self.config.model_dump(mode="json", exclude={"generation_run_id"}),
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(config_json.encode()).hexdigest()[:10]
        return f"northstar-{self.config.seed}-{digest}"

    def _generate_case(
        self,
        rng: Random,
        calendar: BusinessCalendar,
        run_id: str,
        case_index: int,
    ) -> tuple[
        ReferralCase,
        tuple[ReferralEvent, ...],
        CaseGroundTruth,
        tuple[EventGroundTruth, ...],
        tuple[DuplicateSourceAttempt, ...],
    ]:
        config = self.config
        deviations = config.deviations
        operations = config.operations
        bottleneck_config = config.bottlenecks
        referral_source = _weighted_choice(rng, operations.referral_source_mix)
        service_line = _weighted_choice(rng, operations.service_line_mix)
        source_system = _weighted_choice(rng, operations.source_system_mix)
        outcome = _weighted_choice(
            rng,
            {
                ReferralStatus.COMPLETED: config.outcomes.completed,
                ReferralStatus.CANCELLED: config.outcomes.cancelled,
                ReferralStatus.REJECTED: config.outcomes.rejected,
                ReferralStatus.AWAITING_INFORMATION: config.outcomes.stuck,
            },
        )
        received_at = calendar.random_arrival(rng, config)
        case_id = uuid5(GENERATION_NAMESPACE, f"{run_id}:case:{case_index}")
        builder = _CaseBuilder(
            run_id=run_id,
            case_index=case_index,
            case_id=case_id,
            source_system=source_system,
        )
        path = ["standard"]
        bottlenecks: list[BottleneckLabel] = []
        defects: list[DefectType] = []
        has_rework = False
        has_handoff = False

        def ingestion_delay() -> float:
            return rng.uniform(1, 2)

        submitted_at = received_at - timedelta(minutes=rng.uniform(10, 120))
        builder.add(
            event_type=EventType.REFERRAL_SUBMITTED,
            event_at=submitted_at,
            actor_type=ActorType.REFERRER,
            actor_identifier="REFERRER-FICTIONAL",
            channel=(
                CommunicationChannel.SECURE_EMAIL
                if source_system is SourceSystem.SECURE_EMAIL
                else CommunicationChannel.PORTAL
            ),
            ingestion_delay_minutes=ingestion_delay(),
        )
        builder.add(
            event_type=EventType.REFERRAL_RECEIVED,
            event_at=received_at,
            actor_type=ActorType.SYSTEM,
            ingestion_delay_minutes=ingestion_delay(),
        )
        current = calendar.add_work_hours(
            received_at,
            calendar.sample_duration(rng, operations.completeness_check_delay),
        )
        admin_actor = rng.choice(operations.admin_actor_ids)
        builder.add(
            event_type=EventType.COMPLETENESS_CHECK_COMPLETED,
            event_at=current,
            actor_type=ActorType.ADMIN_STAFF,
            actor_identifier=admin_actor,
            source_system=SourceSystem.ADMIN_SYSTEM,
            manual=True,
            ingestion_delay_minutes=ingestion_delay(),
        )

        if outcome is ReferralStatus.REJECTED:
            path.append("rejected")
            current = calendar.add_work_hours(current, rng.uniform(0.25, 2))
            builder.add(
                event_type=EventType.REFERRAL_REJECTED,
                event_at=current,
                actor_type=ActorType.ADMIN_STAFF,
                actor_identifier=admin_actor,
                source_system=SourceSystem.ADMIN_SYSTEM,
                manual=True,
                reason_code=rng.choice(
                    (ReasonCode.OUT_OF_SCOPE_SERVICE, ReasonCode.INVALID_REFERRAL_SOURCE)
                ),
                ingestion_delay_minutes=ingestion_delay(),
            )
        else:
            incomplete_rate = deviations.initially_incomplete
            if referral_source is bottleneck_config.incomplete_referral_source:
                incomplete_rate *= bottleneck_config.incomplete_rate_multiplier
            is_incomplete = _probability(rng, incomplete_rate)
            if is_incomplete:
                path.append("incomplete")
                if referral_source is bottleneck_config.incomplete_referral_source:
                    bottlenecks.append(BottleneckLabel.INCOMPLETE_REFERRALS)
                loops = 1 + int(_probability(rng, deviations.repeated_missing_information))
                for loop_index in range(loops):
                    current = calendar.add_work_hours(current, rng.uniform(0.1, 0.75))
                    builder.add(
                        event_type=EventType.MISSING_INFORMATION_REQUESTED,
                        event_at=current,
                        actor_type=ActorType.ADMIN_STAFF,
                        actor_identifier=admin_actor,
                        source_system=SourceSystem.ADMIN_SYSTEM,
                        channel=CommunicationChannel.SECURE_EMAIL,
                        manual=True,
                        reason_code=(
                            ReasonCode.MISSING_ADMINISTRATIVE_DETAILS
                            if loop_index == 0
                            else ReasonCode.INVALID_ADMINISTRATIVE_DETAILS
                        ),
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                    if outcome is ReferralStatus.AWAITING_INFORMATION:
                        current += timedelta(days=rng.uniform(5, 12))
                        builder.add(
                            event_type=EventType.PATIENT_NO_RESPONSE,
                            event_at=current,
                            actor_type=ActorType.ADMIN_STAFF,
                            actor_identifier=admin_actor,
                            source_system=SourceSystem.ADMIN_SYSTEM,
                            manual=True,
                            reason_code=ReasonCode.PATIENT_UNREACHABLE,
                            ingestion_delay_minutes=ingestion_delay(),
                        )
                        path.append("stuck_missing_information")
                        break
                    current += timedelta(
                        hours=calendar.sample_duration(
                            rng, operations.missing_information_response_delay
                        )
                    )
                    builder.add(
                        event_type=EventType.MISSING_INFORMATION_RECEIVED,
                        event_at=current,
                        actor_type=ActorType.REFERRER,
                        actor_identifier="REFERRER-FICTIONAL",
                        channel=CommunicationChannel.SECURE_EMAIL,
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                    current = calendar.add_work_hours(current, rng.uniform(0.5, 2))
                    builder.add(
                        event_type=EventType.COMPLETENESS_CHECK_COMPLETED,
                        event_at=current,
                        actor_type=ActorType.ADMIN_STAFF,
                        actor_identifier=admin_actor,
                        source_system=SourceSystem.ADMIN_SYSTEM,
                        manual=True,
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                has_rework = True
                if loops > 1:
                    path.append("repeated_information")
            elif _probability(rng, deviations.repeated_completeness_check):
                current = calendar.add_work_hours(current, rng.uniform(0.25, 1.5))
                builder.add(
                    event_type=EventType.COMPLETENESS_CHECK_COMPLETED,
                    event_at=current,
                    actor_type=ActorType.ADMIN_STAFF,
                    actor_identifier=admin_actor,
                    source_system=SourceSystem.ADMIN_SYSTEM,
                    manual=True,
                    ingestion_delay_minutes=ingestion_delay(),
                )
                path.append("repeated_check")
                has_rework = True

            if outcome is not ReferralStatus.AWAITING_INFORMATION or not is_incomplete:
                current = calendar.add_work_hours(
                    current,
                    calendar.sample_duration(rng, operations.categorisation_duration),
                )
                builder.add(
                    event_type=EventType.REFERRAL_CATEGORISED,
                    event_at=current,
                    actor_type=ActorType.ADMIN_STAFF,
                    actor_identifier=admin_actor,
                    source_system=SourceSystem.ADMIN_SYSTEM,
                    manual=True,
                    ingestion_delay_minutes=ingestion_delay(),
                )
                if _probability(rng, deviations.recategorisation):
                    current = calendar.add_work_hours(current, rng.uniform(1, 5))
                    builder.add(
                        event_type=EventType.REFERRAL_RECATEGORISED,
                        event_at=current,
                        actor_type=ActorType.ADMIN_STAFF,
                        actor_identifier=rng.choice(operations.admin_actor_ids),
                        source_system=SourceSystem.ADMIN_SYSTEM,
                        manual=True,
                        reason_code=ReasonCode.INCORRECT_CATEGORY,
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                    path.append("recategorised")
                    has_rework = True

                assignment_delay = calendar.sample_duration(rng, operations.team_assignment_delay)
                if service_line is bottleneck_config.congested_service_line:
                    assignment_delay *= bottleneck_config.assignment_delay_multiplier
                    bottlenecks.append(BottleneckLabel.ASSIGNMENT_CONGESTION)
                current = calendar.add_work_hours(current, assignment_delay)
                team = rng.choice(operations.team_allocation[service_line])
                builder.add(
                    event_type=EventType.CLINICAL_TEAM_ASSIGNED,
                    event_at=current,
                    actor_type=ActorType.ADMIN_STAFF,
                    actor_identifier=admin_actor,
                    source_system=SourceSystem.ADMIN_SYSTEM,
                    manual=True,
                    ingestion_delay_minutes=ingestion_delay(),
                )

                reassignment_rate = deviations.team_reassignment
                if service_line is bottleneck_config.handoff_service_line:
                    reassignment_rate *= bottleneck_config.reassignment_rate_multiplier
                if _probability(rng, reassignment_rate):
                    reassignment_delay = calendar.sample_duration(
                        rng, operations.reassignment_delay
                    )
                    if service_line is bottleneck_config.handoff_service_line:
                        reassignment_delay *= bottleneck_config.reassignment_delay_multiplier
                        bottlenecks.append(BottleneckLabel.HANDOFF_COST)
                    current = calendar.add_work_hours(current, reassignment_delay)
                    alternative_teams = [
                        candidate
                        for candidate in operations.team_allocation[service_line]
                        if candidate != team
                    ]
                    team = rng.choice(alternative_teams or [team])
                    builder.add(
                        event_type=EventType.CLINICAL_TEAM_REASSIGNED,
                        event_at=current,
                        actor_type=ActorType.CLINICAL_TEAM,
                        actor_identifier=team,
                        source_system=SourceSystem.ADMIN_SYSTEM,
                        manual=True,
                        reason_code=ReasonCode.CAPACITY_REBALANCE,
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                    path.append("reassigned")
                    has_rework = True
                    has_handoff = True

                current = calendar.add_work_hours(current, rng.uniform(0.5, 4))
                scheduling_actor = rng.choice(operations.scheduling_actor_ids)
                builder.add(
                    event_type=EventType.APPOINTMENT_SCHEDULING_STARTED,
                    event_at=current,
                    actor_type=ActorType.SCHEDULING_STAFF,
                    actor_identifier=scheduling_actor,
                    source_system=SourceSystem.SCHEDULING_SYSTEM,
                    manual=True,
                    ingestion_delay_minutes=ingestion_delay(),
                )
                failure_rate = deviations.failed_scheduling
                if service_line is bottleneck_config.scheduling_friction_service_line:
                    failure_rate *= bottleneck_config.scheduling_failure_multiplier
                failed_scheduling = _probability(rng, failure_rate)
                if failed_scheduling:
                    failure_count = 1 + int(rng.random() < 0.25)
                    if service_line is bottleneck_config.scheduling_friction_service_line:
                        bottlenecks.append(BottleneckLabel.SCHEDULING_FRICTION)
                    for _ in range(failure_count):
                        current = calendar.add_work_hours(current, rng.uniform(0.5, 2))
                        builder.add(
                            event_type=EventType.APPOINTMENT_SCHEDULING_FAILED,
                            event_at=current,
                            actor_type=ActorType.SCHEDULING_STAFF,
                            actor_identifier=scheduling_actor,
                            source_system=SourceSystem.SCHEDULING_SYSTEM,
                            manual=True,
                            reason_code=rng.choice(
                                (
                                    ReasonCode.NO_APPOINTMENT_SLOT,
                                    ReasonCode.PATIENT_UNAVAILABLE,
                                )
                            ),
                            ingestion_delay_minutes=ingestion_delay(),
                        )
                        current = calendar.add_work_hours(
                            current,
                            calendar.sample_duration(rng, operations.failed_scheduling_delay),
                        )
                        builder.add(
                            event_type=EventType.APPOINTMENT_SCHEDULING_STARTED,
                            event_at=current,
                            actor_type=ActorType.SCHEDULING_STAFF,
                            actor_identifier=scheduling_actor,
                            source_system=SourceSystem.SCHEDULING_SYSTEM,
                            manual=True,
                            ingestion_delay_minutes=ingestion_delay(),
                        )
                    path.append("failed_scheduling")
                    has_rework = True

                if outcome is ReferralStatus.AWAITING_INFORMATION:
                    current += timedelta(days=rng.uniform(7, 16))
                    builder.add(
                        event_type=EventType.PATIENT_NO_RESPONSE,
                        event_at=current,
                        actor_type=ActorType.SCHEDULING_STAFF,
                        actor_identifier=scheduling_actor,
                        source_system=SourceSystem.SCHEDULING_SYSTEM,
                        manual=True,
                        reason_code=ReasonCode.PATIENT_UNREACHABLE,
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                    path.append("stuck_scheduling")
                elif outcome is ReferralStatus.CANCELLED:
                    if _probability(rng, deviations.patient_non_response):
                        current += timedelta(days=rng.uniform(2, 7))
                        builder.add(
                            event_type=EventType.PATIENT_NO_RESPONSE,
                            event_at=current,
                            actor_type=ActorType.SCHEDULING_STAFF,
                            actor_identifier=scheduling_actor,
                            source_system=SourceSystem.SCHEDULING_SYSTEM,
                            manual=True,
                            reason_code=ReasonCode.PATIENT_UNREACHABLE,
                            ingestion_delay_minutes=ingestion_delay(),
                        )
                        cancellation_reason = ReasonCode.PATIENT_UNREACHABLE
                    else:
                        cancellation_reason = ReasonCode.PATIENT_CANCELLED
                    current = calendar.add_work_hours(current, rng.uniform(0.25, 3))
                    builder.add(
                        event_type=EventType.REFERRAL_CANCELLED,
                        event_at=current,
                        actor_type=ActorType.ADMIN_STAFF,
                        actor_identifier=admin_actor,
                        source_system=SourceSystem.ADMIN_SYSTEM,
                        manual=True,
                        reason_code=cancellation_reason,
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                    path.append("cancelled")
                else:
                    booking_delay = calendar.sample_duration(
                        rng, operations.appointment_booking_delay
                    )
                    if service_line is bottleneck_config.scheduling_friction_service_line:
                        booking_delay *= 1.2
                    current = calendar.add_work_hours(current, booking_delay)
                    builder.add(
                        event_type=EventType.APPOINTMENT_BOOKED,
                        event_at=current,
                        actor_type=ActorType.SCHEDULING_STAFF,
                        actor_identifier=scheduling_actor,
                        source_system=SourceSystem.SCHEDULING_SYSTEM,
                        manual=True,
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                    current += timedelta(
                        hours=calendar.sample_duration(rng, operations.notification_delay)
                    )
                    builder.add(
                        event_type=EventType.PATIENT_NOTIFIED,
                        event_at=current,
                        actor_type=ActorType.SYSTEM,
                        source_system=SourceSystem.SCHEDULING_SYSTEM,
                        channel=CommunicationChannel.SMS,
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                    current = calendar.add_work_hours(current, rng.uniform(0.1, 1))
                    builder.add(
                        event_type=EventType.REFERRAL_COMPLETED,
                        event_at=current,
                        actor_type=ActorType.ADMIN_STAFF,
                        actor_identifier=admin_actor,
                        source_system=SourceSystem.ADMIN_SYSTEM,
                        manual=True,
                        ingestion_delay_minutes=ingestion_delay(),
                    )
                    path.append("completed")

        case_events, case_defects, truth_events, attempts = self._apply_defects(
            rng, run_id, case_index, builder.events
        )
        defects.extend(case_defects)
        terminal_status = outcome
        closed_at = (
            case_events[-1].event_at
            if terminal_status
            in {ReferralStatus.COMPLETED, ReferralStatus.CANCELLED, ReferralStatus.REJECTED}
            else None
        )
        case = ReferralCase(
            id=case_id,
            external_source_id=(
                f"NSC-REF-{hashlib.sha256(run_id.encode()).hexdigest()[:8].upper()}{case_index:08}"
            ),
            referral_source=referral_source,
            service_line=service_line,
            status=terminal_status,
            received_at=received_at,
            closed_at=closed_at,
            is_synthetic=True,
            schema_version=1,
            created_at=received_at,
            updated_at=max(event.ingested_at for event in case_events),
        )
        truth = CaseGroundTruth(
            case_id=case_id,
            intended_outcome=terminal_status,
            intended_path=tuple(path),
            bottlenecks=tuple(dict.fromkeys(bottlenecks)),
            defects=tuple(dict.fromkeys(defects)),
            has_rework=has_rework,
            has_handoff=has_handoff,
            is_intentionally_stuck=terminal_status is ReferralStatus.AWAITING_INFORMATION,
        )
        return case, tuple(case_events), truth, tuple(truth_events), tuple(attempts)

    def _apply_defects(
        self,
        rng: Random,
        run_id: str,
        case_index: int,
        original_events: Sequence[ReferralEvent],
    ) -> tuple[
        list[ReferralEvent],
        list[DefectType],
        list[EventGroundTruth],
        list[DuplicateSourceAttempt],
    ]:
        rates = self.config.deviations
        events = list(original_events)
        case_defects: list[DefectType] = []
        event_defects: dict[UUID, list[DefectType]] = {event.id: [] for event in events}
        attempts: list[DuplicateSourceAttempt] = []

        def replace(index: int, **updates: object) -> None:
            payload = events[index].model_dump()
            payload.update(updates)
            events[index] = ReferralEvent.model_validate(payload)

        if _probability(rng, rates.missing_optional_actor):
            replace(0, actor_identifier=None)
            case_defects.append(DefectType.MISSING_OPTIONAL_ACTOR)
            event_defects[events[0].id].append(DefectType.MISSING_OPTIONAL_ACTOR)
        if _probability(rng, rates.unexpected_channel):
            replace(1, channel=CommunicationChannel.LETTER)
            case_defects.append(DefectType.UNEXPECTED_CHANNEL)
            event_defects[events[1].id].append(DefectType.UNEXPECTED_CHANNEL)
        if _probability(rng, rates.source_identifier_inconsistency):
            target = min(2, len(events) - 1)
            replace(target, source_system=SourceSystem.MANUAL_ENTRY)
            case_defects.append(DefectType.SOURCE_IDENTIFIER_INCONSISTENCY)
            event_defects[events[target].id].append(DefectType.SOURCE_IDENTIFIER_INCONSISTENCY)
        if _probability(rng, rates.delayed_ingestion):
            target = len(events) - 1
            replace(
                target,
                ingested_at=events[target].event_at + timedelta(hours=rng.uniform(48, 96)),
            )
            case_defects.append(DefectType.DELAYED_INGESTION)
            event_defects[events[target].id].append(DefectType.DELAYED_INGESTION)
        if len(events) > 2 and _probability(rng, rates.out_of_order_ingestion):
            target = rng.randrange(0, len(events) - 1)
            replace(
                target,
                ingested_at=events[target + 1].ingested_at + timedelta(hours=rng.uniform(2, 12)),
            )
            case_defects.append(DefectType.OUT_OF_ORDER_INGESTION)
            event_defects[events[target].id].append(DefectType.OUT_OF_ORDER_INGESTION)

        for defect, rate in (
            (DefectType.DUPLICATE_SOURCE_EVENT, rates.duplicate_source_event),
            (DefectType.SOURCE_RETRY, rates.source_retry),
        ):
            if _probability(rng, rate):
                canonical = events[1]
                attempt_id = uuid5(
                    GENERATION_NAMESPACE,
                    f"{run_id}:case:{case_index}:attempt:{defect.value}",
                )
                attempts.append(
                    DuplicateSourceAttempt(
                        attempted_event_id=attempt_id,
                        canonical_event_id=canonical.id,
                        source_system=canonical.source_system.value,
                        external_event_id=canonical.external_event_id,
                        defect=defect,
                    )
                )
                case_defects.append(defect)

        truth_events = [
            EventGroundTruth(event_id=event.id, defects=tuple(event_defects[event.id]))
            for event in events
            if event_defects[event.id]
        ]
        return events, case_defects, truth_events, attempts
