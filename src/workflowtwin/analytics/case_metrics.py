"""Case-level operational metrics calculated from canonical event semantics."""

from collections import Counter
from datetime import datetime
from itertools import pairwise

from workflowtwin.analytics.calendar import AnalysisCalendar
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.models import (
    CaseMetrics,
    MetricName,
    MetricPrecision,
    MetricResult,
    MetricStatus,
)
from workflowtwin.analytics.timelines import CaseTimeline
from workflowtwin.domain.referrals.enums import TERMINAL_STATUSES, ActorType, EventType
from workflowtwin.domain.referrals.models import ReferralEvent

TERMINAL_EVENT_TYPES = {
    EventType.REFERRAL_COMPLETED,
    EventType.REFERRAL_CANCELLED,
    EventType.REFERRAL_REJECTED,
    EventType.REFERRAL_CLOSED_OTHER,
}
INTERNAL_ACTORS = {
    ActorType.ADMIN_STAFF,
    ActorType.CLINICAL_TEAM,
    ActorType.SCHEDULING_STAFF,
}
PROGRESS_EVENT_TYPES = {
    EventType.REFERRAL_RECEIVED,
    EventType.COMPLETENESS_CHECK_COMPLETED,
    EventType.MISSING_INFORMATION_REQUESTED,
    EventType.MISSING_INFORMATION_RECEIVED,
    EventType.REFERRAL_CATEGORISED,
    EventType.REFERRAL_RECATEGORISED,
    EventType.CLINICAL_TEAM_ASSIGNED,
    EventType.CLINICAL_TEAM_REASSIGNED,
    EventType.APPOINTMENT_SCHEDULING_STARTED,
    EventType.APPOINTMENT_BOOKED,
    EventType.PATIENT_NOTIFIED,
    *TERMINAL_EVENT_TYPES,
}


def _hours(start: ReferralEvent, end: ReferralEvent) -> float:
    return (end.event_at - start.event_at).total_seconds() / 3600


def _result(
    name: MetricName,
    value: float | int | bool | None,
    unit: str,
    status: MetricStatus,
    precision: MetricPrecision,
    *,
    events: tuple[ReferralEvent, ...] = (),
    start: ReferralEvent | None = None,
    end: ReferralEvent | None = None,
    exclusion: str | None = None,
    warnings: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
) -> MetricResult:
    return MetricResult(
        name=name,
        value=value,
        unit=unit,
        status=status,
        precision=precision,
        source_event_ids=tuple(event.id for event in events),
        start_event_id=start.id if start else None,
        end_event_id=end.id if end else None,
        exclusion_reason=exclusion,
        warnings=warnings,
        assumptions=assumptions,
    )


def _unavailable(name: MetricName, unit: str, reason: str) -> MetricResult:
    return _result(
        name,
        None,
        unit,
        MetricStatus.UNAVAILABLE,
        MetricPrecision.UNAVAILABLE,
        exclusion=reason,
    )


def _invalid(name: MetricName, unit: str, reason: str, *events: ReferralEvent) -> MetricResult:
    return _result(
        name,
        None,
        unit,
        MetricStatus.INVALID_INPUT,
        MetricPrecision.UNAVAILABLE,
        events=events,
        exclusion=reason,
    )


def _unique_events(events: list[ReferralEvent]) -> tuple[ReferralEvent, ...]:
    seen_ids = set()
    unique = []
    for event in events:
        if event.id not in seen_ids:
            seen_ids.add(event.id)
            unique.append(event)
    return tuple(unique)


def calculate_case_metrics(timeline: CaseTimeline, config: AnalysisConfig) -> CaseMetrics:
    """Calculate all version 1 metrics without accessing synthetic ground truth."""
    events = timeline.events
    event_position = {event.id: index for index, event in enumerate(events)}
    by_type: dict[EventType, list[ReferralEvent]] = {}
    for event in events:
        by_type.setdefault(event.event_type, []).append(event)
    received = next(iter(by_type.get(EventType.REFERRAL_RECEIVED, [])), None)
    terminal_events = [event for event in events if event.event_type in TERMINAL_EVENT_TYPES]
    terminal = terminal_events[0] if terminal_events else None
    metrics: dict[MetricName, MetricResult] = {}

    if received is None:
        metrics[MetricName.CASE_DURATION] = _unavailable(
            MetricName.CASE_DURATION, "hours", "missing referral_received event"
        )
        metrics[MetricName.CYCLE_TIME] = _unavailable(
            MetricName.CYCLE_TIME, "hours", "missing referral_received event"
        )
    elif terminal is not None and terminal.event_at < received.event_at:
        metrics[MetricName.CASE_DURATION] = _invalid(
            MetricName.CASE_DURATION,
            "hours",
            "terminal event precedes referral_received",
            received,
            terminal,
        )
        metrics[MetricName.CYCLE_TIME] = _invalid(
            MetricName.CYCLE_TIME,
            "hours",
            "terminal event precedes referral_received",
            received,
            terminal,
        )
    elif terminal is not None:
        duration = _hours(received, terminal)
        warning = (
            ("multiple terminal events; first event-time terminal used",)
            if len(terminal_events) > 1
            else ()
        )
        metrics[MetricName.CASE_DURATION] = _result(
            MetricName.CASE_DURATION,
            duration,
            "hours",
            MetricStatus.CALCULATED,
            MetricPrecision.EXACT,
            events=(received, terminal),
            start=received,
            end=terminal,
            warnings=warning,
        )
        metrics[MetricName.CYCLE_TIME] = _result(
            MetricName.CYCLE_TIME,
            duration,
            "hours",
            MetricStatus.CALCULATED,
            MetricPrecision.EXACT,
            events=(received, terminal),
            start=received,
            end=terminal,
            warnings=warning,
            assumptions=("cycle time includes processing and waiting",),
        )
    elif config.include_open_cases and config.analysis_cutoff >= received.event_at:
        age = (config.analysis_cutoff - received.event_at).total_seconds() / 3600
        metrics[MetricName.CASE_DURATION] = _result(
            MetricName.CASE_DURATION,
            age,
            "hours",
            MetricStatus.PARTIAL,
            MetricPrecision.PARTIAL,
            events=(received,),
            start=received,
            exclusion="open-case age is censored at analysis cutoff",
            assumptions=("open age is not included in closed duration summaries",),
        )
        metrics[MetricName.CYCLE_TIME] = _result(
            MetricName.CYCLE_TIME,
            None,
            "hours",
            MetricStatus.NOT_APPLICABLE,
            MetricPrecision.UNAVAILABLE,
            events=(received,),
            start=received,
            exclusion="cycle time requires a terminal event",
        )
    else:
        metrics[MetricName.CASE_DURATION] = _result(
            MetricName.CASE_DURATION,
            None,
            "hours",
            MetricStatus.EXCLUDED,
            MetricPrecision.UNAVAILABLE,
            exclusion="open cases excluded by configuration",
        )
        metrics[MetricName.CYCLE_TIME] = _result(
            MetricName.CYCLE_TIME,
            None,
            "hours",
            MetricStatus.NOT_APPLICABLE,
            MetricPrecision.UNAVAILABLE,
            exclusion="cycle time requires a terminal event",
        )

    manual_events = tuple(event for event in events if event.requires_manual_work)
    metrics[MetricName.MANUAL_TOUCHES] = _result(
        MetricName.MANUAL_TOUCHES,
        len(manual_events),
        "events",
        MetricStatus.CALCULATED,
        MetricPrecision.EXACT,
        events=manual_events,
    )
    processing_hours = len(manual_events) * config.manual_touch_minutes_proxy / 60
    metrics[MetricName.PROCESSING_TIME] = _result(
        MetricName.PROCESSING_TIME,
        processing_hours,
        "hours",
        MetricStatus.ESTIMATED,
        MetricPrecision.ESTIMATED,
        events=manual_events,
        assumptions=(
            f"each manual touch represents {config.manual_touch_minutes_proxy:g} minutes",
            "point events do not contain observed effort duration",
        ),
    )

    responsible_events = [
        event
        for event in events
        if event.actor_type in INTERNAL_ACTORS and event.actor_identifier is not None
    ]
    handoff_events: list[ReferralEvent] = []
    for previous, current in pairwise(responsible_events):
        if previous.actor_identifier != current.actor_identifier:
            handoff_events.extend((previous, current))
    unique_handoff_events = _unique_events(handoff_events)
    handoff_count = sum(
        previous.actor_identifier != current.actor_identifier
        for previous, current in pairwise(responsible_events)
    )
    metrics[MetricName.HANDOFFS] = _result(
        MetricName.HANDOFFS,
        handoff_count,
        "transitions",
        MetricStatus.ESTIMATED,
        MetricPrecision.ESTIMATED,
        events=unique_handoff_events,
        assumptions=("missing actor identifiers do not create handoffs",),
    )

    counts = Counter(event.event_type for event in events)
    inferred_rework_count = max(0, counts[EventType.COMPLETENESS_CHECK_COMPLETED] - 1) + max(
        0, counts[EventType.MISSING_INFORMATION_REQUESTED] - 1
    )
    explicit_rework_count = (
        counts[EventType.REFERRAL_RECATEGORISED]
        + counts[EventType.CLINICAL_TEAM_REASSIGNED]
        + counts[EventType.APPOINTMENT_SCHEDULING_FAILED]
    )
    rework_count = inferred_rework_count + explicit_rework_count
    rework_events = tuple(
        event
        for event in events
        if event.event_type
        in {
            EventType.REFERRAL_RECATEGORISED,
            EventType.CLINICAL_TEAM_REASSIGNED,
            EventType.APPOINTMENT_SCHEDULING_FAILED,
        }
    )
    metrics[MetricName.REWORK_COUNT] = _result(
        MetricName.REWORK_COUNT,
        rework_count,
        "events",
        MetricStatus.ESTIMATED if inferred_rework_count else MetricStatus.CALCULATED,
        MetricPrecision.ESTIMATED if inferred_rework_count else MetricPrecision.EXACT,
        events=rework_events,
        assumptions=("repeat counts follow metric definition version 1",),
    )
    metrics[MetricName.FAILED_SCHEDULING] = _result(
        MetricName.FAILED_SCHEDULING,
        counts[EventType.APPOINTMENT_SCHEDULING_FAILED],
        "events",
        MetricStatus.CALCULATED,
        MetricPrecision.EXACT,
        events=tuple(by_type.get(EventType.APPOINTMENT_SCHEDULING_FAILED, [])),
    )
    metrics[MetricName.REASSIGNMENTS] = _result(
        MetricName.REASSIGNMENTS,
        counts[EventType.CLINICAL_TEAM_REASSIGNED],
        "events",
        MetricStatus.CALCULATED,
        MetricPrecision.EXACT,
        events=tuple(by_type.get(EventType.CLINICAL_TEAM_REASSIGNED, [])),
    )
    last_progress_event = next(
        (event for event in reversed(events) if event.event_type in PROGRESS_EVENT_TYPES),
        None,
    )
    if terminal is not None:
        metrics[MetricName.IS_STUCK] = _result(
            MetricName.IS_STUCK,
            False,
            "boolean",
            MetricStatus.CALCULATED,
            MetricPrecision.EXACT,
            events=(terminal,),
        )
    elif last_progress_event is not None and config.analysis_cutoff >= last_progress_event.event_at:
        inactive_hours = (
            config.analysis_cutoff - last_progress_event.event_at
        ).total_seconds() / 3600
        metrics[MetricName.IS_STUCK] = _result(
            MetricName.IS_STUCK,
            inactive_hours >= config.stuck_threshold_hours,
            "boolean",
            MetricStatus.CALCULATED,
            MetricPrecision.EXACT,
            events=(last_progress_event,),
            assumptions=(
                f"open case is stuck after {config.stuck_threshold_hours:g} inactive hours",
            ),
        )
    else:
        metrics[MetricName.IS_STUCK] = _unavailable(
            MetricName.IS_STUCK,
            "boolean",
            "no event at or before the analysis cutoff",
        )

    first_check = next(iter(by_type.get(EventType.COMPLETENESS_CHECK_COMPLETED, [])), None)
    first_category = next(iter(by_type.get(EventType.REFERRAL_CATEGORISED, [])), None)
    if first_check is None:
        metrics[MetricName.FIRST_PASS_COMPLETE] = _unavailable(
            MetricName.FIRST_PASS_COMPLETE, "boolean", "missing completeness check"
        )
    else:
        check_position = event_position[first_check.id]
        category_position = event_position[first_category.id] if first_category else len(events)
        requests_after_check = [
            event
            for event in by_type.get(EventType.MISSING_INFORMATION_REQUESTED, [])
            if check_position < event_position[event.id] < category_position
        ]
        if first_category is None and not requests_after_check:
            metrics[MetricName.FIRST_PASS_COMPLETE] = _unavailable(
                MetricName.FIRST_PASS_COMPLETE,
                "boolean",
                "cannot establish pass without categorisation or missing-information request",
            )
        else:
            metrics[MetricName.FIRST_PASS_COMPLETE] = _result(
                MetricName.FIRST_PASS_COMPLETE,
                not requests_after_check,
                "boolean",
                MetricStatus.ESTIMATED,
                MetricPrecision.ESTIMATED,
                events=(first_check, *requests_after_check),
                assumptions=("pass is inferred from events before first categorisation",),
            )

    if received and first_check and first_check.event_at < received.event_at:
        metrics[MetricName.TIME_TO_FIRST_CHECK] = _invalid(
            MetricName.TIME_TO_FIRST_CHECK,
            "hours",
            "completeness check precedes referral_received",
            received,
            first_check,
        )
    elif received and first_check:
        metrics[MetricName.TIME_TO_FIRST_CHECK] = _result(
            MetricName.TIME_TO_FIRST_CHECK,
            _hours(received, first_check),
            "hours",
            MetricStatus.CALCULATED,
            MetricPrecision.EXACT,
            events=(received, first_check),
            start=received,
            end=first_check,
        )
    else:
        metrics[MetricName.TIME_TO_FIRST_CHECK] = _unavailable(
            MetricName.TIME_TO_FIRST_CHECK,
            "hours",
            "missing referral_received or completeness check",
        )
    first_booking = next(iter(by_type.get(EventType.APPOINTMENT_BOOKED, [])), None)
    if received and first_booking and first_booking.event_at < received.event_at:
        metrics[MetricName.TIME_TO_BOOKING] = _invalid(
            MetricName.TIME_TO_BOOKING,
            "hours",
            "appointment booking precedes referral_received",
            received,
            first_booking,
        )
    elif received and first_booking:
        metrics[MetricName.TIME_TO_BOOKING] = _result(
            MetricName.TIME_TO_BOOKING,
            _hours(received, first_booking),
            "hours",
            MetricStatus.CALCULATED,
            MetricPrecision.EXACT,
            events=(received, first_booking),
            start=received,
            end=first_booking,
        )
    else:
        booking_status = (
            MetricStatus.NOT_APPLICABLE
            if timeline.referral_case.status in TERMINAL_STATUSES
            else MetricStatus.UNAVAILABLE
        )
        metrics[MetricName.TIME_TO_BOOKING] = _result(
            MetricName.TIME_TO_BOOKING,
            None,
            "hours",
            booking_status,
            MetricPrecision.UNAVAILABLE,
            exclusion="no appointment_booked event",
        )

    calendar = AnalysisCalendar(config)
    waiting_intervals: list[tuple[ReferralEvent, ReferralEvent | None]] = []
    if received and first_check and event_position[received.id] < event_position[first_check.id]:
        waiting_intervals.append((received, first_check))
    responses = list(by_type.get(EventType.MISSING_INFORMATION_RECEIVED, []))
    used_response_ids = set()
    for request in by_type.get(EventType.MISSING_INFORMATION_REQUESTED, []):
        response = next(
            (
                candidate
                for candidate in responses
                if candidate.id not in used_response_ids
                and event_position[candidate.id] > event_position[request.id]
            ),
            None,
        )
        if response is not None:
            used_response_ids.add(response.id)
        waiting_intervals.append((request, response))
    scheduling_starts = list(by_type.get(EventType.APPOINTMENT_SCHEDULING_STARTED, []))
    assignments = sorted(
        [
            *by_type.get(EventType.CLINICAL_TEAM_ASSIGNED, []),
            *by_type.get(EventType.CLINICAL_TEAM_REASSIGNED, []),
        ],
        key=lambda event: (event.event_at, event.id.hex),
    )
    if assignments and scheduling_starts:
        first_start = scheduling_starts[0]
        prior_assignments = [
            event
            for event in assignments
            if event_position[event.id] < event_position[first_start.id]
        ]
        if prior_assignments:
            waiting_intervals.append((prior_assignments[-1], first_start))
    for failure in by_type.get(EventType.APPOINTMENT_SCHEDULING_FAILED, []):
        next_start = next(
            (
                event
                for event in scheduling_starts
                if event_position[event.id] > event_position[failure.id]
            ),
            None,
        )
        waiting_intervals.append((failure, next_start))

    resolved_intervals: list[tuple[datetime, datetime]] = []
    waiting_sources: list[ReferralEvent] = []
    unmatched = 0
    partial = False
    for start, end in waiting_intervals:
        if end is not None:
            resolved_intervals.append((start.event_at, end.event_at))
            waiting_sources.extend((start, end))
        elif (
            terminal is None
            and config.include_open_cases
            and config.analysis_cutoff >= start.event_at
        ):
            resolved_intervals.append((start.event_at, config.analysis_cutoff))
            waiting_sources.append(start)
            partial = True
        else:
            unmatched += 1
    merged_intervals: list[tuple[datetime, datetime]] = []
    for start_at, end_at in sorted(resolved_intervals):
        if merged_intervals and start_at <= merged_intervals[-1][1]:
            previous_start, previous_end = merged_intervals[-1]
            merged_intervals[-1] = (previous_start, max(previous_end, end_at))
        else:
            merged_intervals.append((start_at, end_at))
    waiting_hours = sum(
        calendar.business_hours_between(start_at, end_at) for start_at, end_at in merged_intervals
    )
    waiting_status = MetricStatus.PARTIAL if partial else MetricStatus.ESTIMATED
    metrics[MetricName.WAITING_TIME] = _result(
        MetricName.WAITING_TIME,
        waiting_hours,
        "business_hours",
        waiting_status,
        MetricPrecision.PARTIAL if partial else MetricPrecision.ESTIMATED,
        events=_unique_events(waiting_sources),
        warnings=((f"{unmatched} unmatched wait interval(s) omitted",) if unmatched else ()),
        assumptions=("only documented non-overlapping wait categories are included",),
    )

    categorisations = sorted(
        [
            *by_type.get(EventType.REFERRAL_CATEGORISED, []),
            *by_type.get(EventType.REFERRAL_RECATEGORISED, []),
        ],
        key=lambda event: (event.event_at, event.id.hex),
    )
    first_assignment = next(iter(by_type.get(EventType.CLINICAL_TEAM_ASSIGNED, [])), None)
    if categorisations and first_assignment:
        prior_categories = [
            event
            for event in categorisations
            if event_position[event.id] < event_position[first_assignment.id]
        ]
        if prior_categories:
            category = prior_categories[-1]
            metrics[MetricName.ASSIGNMENT_WAIT] = _result(
                MetricName.ASSIGNMENT_WAIT,
                calendar.business_hours_between(category.event_at, first_assignment.event_at),
                "business_hours",
                MetricStatus.ESTIMATED,
                MetricPrecision.ESTIMATED,
                events=(category, first_assignment),
                start=category,
                end=first_assignment,
            )
        else:
            metrics[MetricName.ASSIGNMENT_WAIT] = _invalid(
                MetricName.ASSIGNMENT_WAIT,
                "business_hours",
                "team assignment precedes every categorisation event",
                first_assignment,
                *categorisations,
            )
    else:
        metrics[MetricName.ASSIGNMENT_WAIT] = _unavailable(
            MetricName.ASSIGNMENT_WAIT,
            "business_hours",
            "missing categorisation or team assignment",
        )

    ingestion_delays = [
        (event.ingested_at - event.event_at).total_seconds() / 3600 for event in events
    ]
    delayed_events = tuple(
        event
        for event, delay in zip(events, ingestion_delays, strict=True)
        if delay > config.delayed_ingestion_threshold_hours
    )
    metrics[MetricName.MAX_INGESTION_DELAY] = _result(
        MetricName.MAX_INGESTION_DELAY,
        max(ingestion_delays, default=0.0),
        "hours",
        MetricStatus.CALCULATED,
        MetricPrecision.EXACT,
        events=tuple(events),
    )
    metrics[MetricName.DELAYED_EVENTS] = _result(
        MetricName.DELAYED_EVENTS,
        len(delayed_events),
        "events",
        MetricStatus.CALCULATED,
        MetricPrecision.EXACT,
        events=delayed_events,
    )
    metrics[MetricName.OUT_OF_ORDER_INGESTION] = _result(
        MetricName.OUT_OF_ORDER_INGESTION,
        timeline.out_of_order_ingestion,
        "boolean",
        MetricStatus.CALCULATED,
        MetricPrecision.EXACT,
        events=tuple(events),
    )

    return CaseMetrics(
        case_id=timeline.referral_case.id,
        lifecycle_status=timeline.referral_case.status.value,
        referral_source=timeline.referral_case.referral_source.value,
        service_line=timeline.referral_case.service_line.value,
        primary_source_system=timeline.primary_source_system,
        assigned_team=timeline.assigned_team,
        metrics=metrics,
        timeline_warnings=timeline.warnings,
    )
