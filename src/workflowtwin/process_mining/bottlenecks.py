"""Deterministic process bottleneck candidates without causal claims."""

import hashlib
from dataclasses import dataclass
from statistics import median
from uuid import UUID

from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import (
    ConformanceStatus,
    EventLogRecord,
    Materiality,
    NumericSummary,
    ProcessBottleneckCandidate,
    ProcessLog,
    ProcessVariant,
    TraceConformanceResult,
    TransitionStatistics,
)
from workflowtwin.process_mining.statistics import numeric_summary


def _identifier(candidate_type: str, subject: str, cohort: str | None = None) -> str:
    value = f"{candidate_type}\x1f{subject}\x1f{cohort or ''}"
    return f"candidate-{hashlib.sha256(value.encode()).hexdigest()[:16]}"


def _materiality(relative: float | None) -> Materiality:
    if relative is not None and relative >= 0.5:
        return Materiality.STRONG
    if relative is not None and relative >= 0.2:
        return Materiality.MATERIAL
    return Materiality.SMALL


def _candidate(
    *,
    candidate_type: str,
    subject: str,
    case_ids: tuple[UUID, ...],
    case_count: int,
    frequency: int,
    elapsed: list[float],
    config: ProcessMiningConfig,
    comparison: float | None = None,
    observed: float | None = None,
    dimension: str | None = None,
    cohort: str | None = None,
    manual_touch_rate: float | None = None,
    handoff_rate: float | None = None,
    context: str = "descriptive process association",
    elapsed_summary: NumericSummary | None = None,
) -> ProcessBottleneckCandidate:
    absolute = observed - comparison if observed is not None and comparison is not None else None
    relative = absolute / comparison if absolute is not None and comparison else None
    return ProcessBottleneckCandidate(
        candidate_id=_identifier(candidate_type, subject, cohort),
        candidate_type=candidate_type,
        subject=subject,
        cohort_dimension=dimension,
        cohort_value=cohort,
        frequency=frequency,
        case_count=case_count,
        elapsed_hours=elapsed_summary or numeric_summary(elapsed, config.duration_percentiles),
        comparison_value=comparison,
        absolute_difference=absolute,
        relative_difference=relative,
        manual_touch_rate=manual_touch_rate,
        handoff_rate=handoff_rate,
        conformance_context=context,
        supporting_case_ids=case_ids[:25],
        materiality=_materiality(relative),
        warnings=(
            "candidate is associated with observed process behaviour and does not establish "
            "causality",
        ),
    )


def _trace_elapsed(trace_events: tuple[EventLogRecord, ...]) -> float:
    return (trace_events[-1].event_at - trace_events[0].event_at).total_seconds() / 3600


@dataclass(frozen=True, slots=True)
class _TraceFeature:
    case_id: UUID
    referral_source: str
    service_line: str
    elapsed: float
    missing: bool
    assignment_delays: tuple[float, ...]
    scheduling_failed: int
    reassigned: int


def _feature_value(item: _TraceFeature, feature: str) -> bool | int:
    if feature == "missing":
        return item.missing
    if feature == "scheduling_failed":
        return item.scheduling_failed
    if feature == "reassigned":
        return item.reassigned
    raise ValueError(f"unknown trace feature: {feature}")


def _dimension_value(item: _TraceFeature, dimension: str) -> str:
    if dimension == "referral_source":
        return item.referral_source
    if dimension == "service_line":
        return item.service_line
    raise ValueError(f"unknown trace dimension: {dimension}")


def _cohort_candidates(
    process_log: ProcessLog, config: ProcessMiningConfig
) -> list[ProcessBottleneckCandidate]:
    candidates = []
    trace_features = []
    for trace in process_log.traces:
        activities = trace.activities
        first = trace.events[0]
        assignment_delays = [
            (target.event_at - source.event_at).total_seconds() / 3600
            for source, target in zip(trace.events, trace.events[1:], strict=False)
            if source.activity in {"Referral categorised", "Referral recategorised"}
            and target.activity == "Clinical team assigned"
        ]
        trace_features.append(
            _TraceFeature(
                case_id=trace.case_id,
                referral_source=first.referral_source,
                service_line=first.service_line,
                elapsed=_trace_elapsed(trace.events),
                missing="Missing information requested" in activities,
                assignment_delays=tuple(assignment_delays),
                scheduling_failed=activities.count("Scheduling failed"),
                reassigned=activities.count("Clinical team reassigned"),
            )
        )

    def rate(feature: str) -> float:
        return sum(bool(_feature_value(item, feature)) for item in trace_features) / len(
            trace_features
        )

    overall_missing = rate("missing")
    for dimension, feature, candidate_type, subject in (
        (
            "referral_source",
            "missing",
            "referral_source_rework_path",
            "Missing information requested",
        ),
        (
            "service_line",
            "scheduling_failed",
            "service_line_scheduling_retries",
            "Scheduling failed",
        ),
        (
            "service_line",
            "reassigned",
            "service_line_reassignment",
            "Clinical team reassigned",
        ),
    ):
        values = sorted({_dimension_value(item, dimension) for item in trace_features})
        overall = overall_missing if feature == "missing" else rate(feature)
        for value in values:
            members = [
                item for item in trace_features if _dimension_value(item, dimension) == value
            ]
            if len(members) < config.minimum_cohort_size:
                continue
            observed = sum(bool(_feature_value(item, feature)) for item in members) / len(members)
            relative = (observed - overall) / overall if overall else None
            if relative is None or relative < 0.2:
                continue
            case_ids = tuple(sorted((item.case_id for item in members), key=lambda x: x.hex))
            candidates.append(
                _candidate(
                    candidate_type=candidate_type,
                    subject=subject,
                    case_ids=case_ids,
                    case_count=len(members),
                    frequency=sum(int(_feature_value(item, feature)) for item in members),
                    elapsed=[item.elapsed for item in members],
                    config=config,
                    comparison=overall,
                    observed=observed,
                    dimension=dimension,
                    cohort=value,
                )
            )
    all_assignment_delays = [delay for item in trace_features for delay in item.assignment_delays]
    if all_assignment_delays:
        overall_assignment = median(all_assignment_delays)
        for value in sorted({item.service_line for item in trace_features}):
            members = [item for item in trace_features if item.service_line == value]
            delays = [delay for item in members for delay in item.assignment_delays]
            if len(members) < config.minimum_cohort_size or not delays:
                continue
            observed = median(delays)
            relative = (
                (observed - overall_assignment) / overall_assignment if overall_assignment else None
            )
            if relative is None or relative < 0.2:
                continue
            case_ids = tuple(sorted((item.case_id for item in members), key=lambda x: x.hex))
            candidates.append(
                _candidate(
                    candidate_type="service_line_assignment_delay",
                    subject="Referral categorised -> Clinical team assigned",
                    case_ids=case_ids,
                    case_count=len(members),
                    frequency=len(delays),
                    elapsed=delays,
                    config=config,
                    comparison=overall_assignment,
                    observed=observed,
                    dimension="service_line",
                    cohort=value,
                )
            )
    return candidates


def detect_bottleneck_candidates(
    process_log: ProcessLog,
    transitions: tuple[TransitionStatistics, ...],
    variants: tuple[ProcessVariant, ...],
    governed_results: tuple[TraceConformanceResult, ...] | None,
    config: ProcessMiningConfig,
) -> tuple[ProcessBottleneckCandidate, ...]:
    candidates = _cohort_candidates(process_log, config)
    transition_medians = [
        value
        for transition in transitions
        if (value := transition.elapsed_hours.median) is not None
        and transition.frequency >= config.minimum_transition_frequency
    ]
    baseline_transition = median(transition_medians) if transition_medians else None
    for transition in transitions:
        observed = transition.elapsed_hours.median
        if (
            observed is None
            or baseline_transition is None
            or transition.frequency < config.minimum_transition_frequency
            or observed < baseline_transition * 1.5
        ):
            continue
        candidates.append(
            _candidate(
                candidate_type="high_frequency_slow_transition",
                subject=f"{transition.source_activity} -> {transition.target_activity}",
                case_ids=transition.supporting_case_ids,
                case_count=transition.distinct_case_count,
                frequency=transition.frequency,
                elapsed=[observed] * transition.distinct_case_count,
                elapsed_summary=transition.elapsed_hours,
                config=config,
                comparison=baseline_transition,
                observed=observed,
                manual_touch_rate=transition.manual_touch_rate,
                handoff_rate=transition.handoff_rate,
            )
        )
    variant_medians = [
        value for variant in variants if (value := variant.duration_hours.median) is not None
    ]
    baseline_variant = median(variant_medians) if variant_medians else None
    for variant in variants:
        observed = variant.duration_hours.median
        if (
            observed is None
            or baseline_variant is None
            or variant.case_count < config.minimum_variant_frequency
            or observed < baseline_variant * 1.5
        ):
            continue
        candidates.append(
            _candidate(
                candidate_type="variant_elevated_duration",
                subject=variant.variant_id,
                case_ids=variant.representative_case_ids,
                case_count=variant.case_count,
                frequency=variant.case_count,
                elapsed=[observed] * variant.case_count,
                config=config,
                comparison=baseline_variant,
                observed=observed,
                context="variant contains elevated elapsed duration",
            )
        )
    if governed_results:
        nonconforming = [
            result.case_id
            for result in governed_results
            if result.status is not ConformanceStatus.FULLY_CONFORMING
        ]
        if len(nonconforming) >= config.minimum_cohort_size:
            trace_by_case = {trace.case_id: trace for trace in process_log.traces}
            elapsed = [_trace_elapsed(trace_by_case[case_id].events) for case_id in nonconforming]
            candidates.append(
                _candidate(
                    candidate_type="nonconforming_path_duration",
                    subject="governed non-conforming traces",
                    case_ids=tuple(sorted(nonconforming, key=lambda x: x.hex)),
                    case_count=len(nonconforming),
                    frequency=len(nonconforming),
                    elapsed=elapsed,
                    config=config,
                    context="non-conforming paths observed alongside elapsed duration",
                )
            )
    return tuple(sorted(candidates, key=lambda item: item.candidate_id))
