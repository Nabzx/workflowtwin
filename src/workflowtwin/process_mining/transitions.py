"""Explainable activity, transition, and loop statistics."""

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import pairwise
from statistics import fmean
from uuid import UUID

from workflowtwin.analytics.calendar import AnalysisCalendar
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.process_mining.activity_mapping import TERMINAL_ACTIVITIES
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import (
    ActivityStatistics,
    EventLogRecord,
    LoopStatistics,
    ProcessLog,
    TransitionStatistics,
)
from workflowtwin.process_mining.statistics import numeric_summary

INTERNAL_ACTORS = {"admin_staff", "clinical_team", "scheduling_staff"}
REWORK_ACTIVITIES = {
    "Referral recategorised",
    "Clinical team reassigned",
    "Scheduling failed",
}


def transition_id(source: str, target: str) -> str:
    digest = hashlib.sha256(f"{source}\x1f{target}".encode()).hexdigest()[:12]
    return f"transition-{digest}"


def node_id(activity: str) -> str:
    return f"activity-{hashlib.sha256(activity.encode()).hexdigest()[:12]}"


def _handoff(source: EventLogRecord, target: EventLogRecord) -> bool:
    if source.actor_type not in INTERNAL_ACTORS or target.actor_type not in INTERNAL_ACTORS:
        return False
    source_owner = source.team_identifier or source.actor_identifier
    target_owner = target.team_identifier or target.actor_identifier
    return source_owner is not None and target_owner is not None and source_owner != target_owner


@dataclass(frozen=True, slots=True)
class ProcessStatistics:
    activities: tuple[ActivityStatistics, ...]
    transitions: tuple[TransitionStatistics, ...]
    starts: dict[str, int]
    ends: dict[str, int]
    loops: tuple[LoopStatistics, ...]


def calculate_process_statistics(
    process_log: ProcessLog, config: ProcessMiningConfig
) -> ProcessStatistics:
    activity_events: dict[str, list[tuple[UUID, int, EventLogRecord]]] = defaultdict(list)
    transition_occurrences: dict[
        tuple[str, str], list[tuple[UUID, EventLogRecord, EventLogRecord]]
    ] = defaultdict(list)
    starts: Counter[str] = Counter()
    ends: Counter[str] = Counter()
    self_loops: dict[str, list[tuple[UUID, float]]] = defaultdict(list)
    two_step_loops: dict[tuple[str, str], list[tuple[UUID, float]]] = defaultdict(list)
    for trace in process_log.traces:
        starts[trace.events[0].activity] += 1
        ends[trace.events[-1].activity] += 1
        for position, event in enumerate(trace.events):
            activity_events[event.activity].append((trace.case_id, position, event))
        for source, target in pairwise(trace.events):
            transition_occurrences[(source.activity, target.activity)].append(
                (trace.case_id, source, target)
            )
            elapsed_hours = (target.event_at - source.event_at).total_seconds() / 3600
            if source.activity == target.activity:
                self_loops[source.activity].append((trace.case_id, elapsed_hours))
        for first, second, third in zip(
            trace.events, trace.events[1:], trace.events[2:], strict=False
        ):
            if first.activity == third.activity and first.activity != second.activity:
                elapsed = (third.event_at - first.event_at).total_seconds() / 3600
                two_step_loops[(first.activity, second.activity)].append((trace.case_id, elapsed))

    activities = []
    for activity, records in sorted(activity_events.items()):
        counts = Counter(case_id for case_id, _, _ in records)
        activities.append(
            ActivityStatistics(
                activity=activity,
                frequency=len(records),
                distinct_case_count=len(counts),
                manual_work_rate=sum(event.requires_manual_work for _, _, event in records)
                / len(records),
                average_case_position=fmean(position for _, position, _ in records),
                repeated_case_count=sum(count > 1 for count in counts.values()),
            )
        )
    calendar = AnalysisCalendar(AnalysisConfig(reporting_timezone=config.reporting_timezone))
    transitions = []
    for (source_activity, target_activity), occurrences in sorted(transition_occurrences.items()):
        elapsed_values = [
            (target.event_at - source.event_at).total_seconds() / 3600
            for _, source, target in occurrences
        ]
        business = [
            calendar.business_hours_between(source.event_at, target.event_at)
            for _, source, target in occurrences
        ]
        case_ids = tuple(sorted({case_id for case_id, _, _ in occurrences}, key=lambda x: x.hex))
        transitions.append(
            TransitionStatistics(
                transition_id=transition_id(source_activity, target_activity),
                source_activity=source_activity,
                target_activity=target_activity,
                frequency=len(occurrences),
                distinct_case_count=len(case_ids),
                eligible_case_percentage=len(case_ids) / len(process_log.traces),
                elapsed_hours=numeric_summary(elapsed_values, config.duration_percentiles),
                business_hours=numeric_summary(business, config.duration_percentiles),
                manual_touch_rate=sum(
                    source.requires_manual_work or target.requires_manual_work
                    for _, source, target in occurrences
                )
                / len(occurrences),
                handoff_rate=sum(_handoff(source, target) for _, source, target in occurrences)
                / len(occurrences),
                rework_rate=sum(
                    target.activity in REWORK_ACTIVITIES or source.activity == target.activity
                    for _, source, target in occurrences
                )
                / len(occurrences),
                terminal_transition=target_activity in TERMINAL_ACTIVITIES,
                supporting_case_ids=case_ids[:25],
            )
        )
    loops = []
    for activity, loop_records in sorted(self_loops.items()):
        case_ids = tuple(sorted({case_id for case_id, _ in loop_records}, key=lambda x: x.hex))
        durations = [duration for _, duration in loop_records]
        loops.append(
            LoopStatistics(
                loop_id=f"self-{transition_id(activity, activity)}",
                loop_type="self_loop",
                activities=(activity,),
                occurrence_count=len(loop_records),
                distinct_case_count=len(case_ids),
                median_elapsed_hours=numeric_summary(durations, (0.5,)).median,
                supporting_case_ids=case_ids[:25],
            )
        )
    for activities_key, loop_records in sorted(two_step_loops.items()):
        case_ids = tuple(sorted({case_id for case_id, _ in loop_records}, key=lambda x: x.hex))
        durations = [duration for _, duration in loop_records]
        loops.append(
            LoopStatistics(
                loop_id=f"two-step-{transition_id(*activities_key)}",
                loop_type="two_step_loop",
                activities=activities_key,
                occurrence_count=len(loop_records),
                distinct_case_count=len(case_ids),
                median_elapsed_hours=numeric_summary(durations, (0.5,)).median,
                supporting_case_ids=case_ids[:25],
            )
        )
    return ProcessStatistics(
        activities=tuple(activities),
        transitions=tuple(transitions),
        starts=dict(sorted(starts.items())),
        ends=dict(sorted(ends.items())),
        loops=tuple(sorted(loops, key=lambda item: item.loop_id)),
    )
