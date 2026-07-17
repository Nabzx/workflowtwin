"""Typed strict/governed conformance and understandable deviation taxonomy."""

import hashlib
from collections import Counter, defaultdict
from statistics import fmean, median
from time import monotonic
from uuid import UUID

from workflowtwin.process_mining.adapters.pm4py import (
    Pm4pyAdapter,
    Pm4pyAdapterError,
    ReplayDiagnostic,
)
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import (
    CohortConformance,
    ConformanceStatus,
    ConformanceSummary,
    Deviation,
    DeviationCategory,
    ProcessLog,
    ProcessTrace,
    TraceConformanceResult,
)
from workflowtwin.process_mining.reference_models import (
    GOVERNED_ACTIVITIES,
    STRICT_REFERENCE_ID,
    STRICT_SEQUENCE,
    TERMINALS,
)


def _deviation(
    trace: ProcessTrace,
    category: DeviationCategory,
    description: str,
    activity: str | None = None,
    position: int | None = None,
) -> Deviation:
    identity = f"{trace.case_id}:{category.value}:{activity}:{position}:{description}"
    source_ids = tuple(
        event.event_id for event in trace.events if activity is None or event.activity == activity
    )
    return Deviation(
        deviation_id=f"deviation-{hashlib.sha256(identity.encode()).hexdigest()[:16]}",
        category=category,
        activity=activity,
        position=position,
        description=description,
        source_event_ids=source_ids,
    )


def _strict_deviations(trace: ProcessTrace) -> tuple[Deviation, ...]:
    observed = trace.activities
    deviations = []
    expected_counts = Counter(STRICT_SEQUENCE)
    observed_counts = Counter(observed)
    for activity in STRICT_SEQUENCE:
        if activity not in observed_counts:
            deviations.append(
                _deviation(
                    trace,
                    DeviationCategory.MISSING_ACTIVITY,
                    f"strict reference expects {activity}",
                    activity,
                )
            )
    for position, activity in enumerate(observed):
        if activity not in expected_counts:
            deviations.append(
                _deviation(
                    trace,
                    DeviationCategory.UNEXPECTED_ACTIVITY,
                    f"strict reference does not contain {activity}",
                    activity,
                    position,
                )
            )
    for activity, count in observed_counts.items():
        if activity in expected_counts and count > expected_counts[activity]:
            deviations.append(
                _deviation(
                    trace,
                    DeviationCategory.ACTIVITY_REPEATED,
                    f"{activity} occurs {count} times",
                    activity,
                )
            )
    present_positions = [
        STRICT_SEQUENCE.index(activity) for activity in observed if activity in STRICT_SEQUENCE
    ]
    if present_positions != sorted(present_positions):
        deviations.append(
            _deviation(
                trace,
                DeviationCategory.UNEXPECTED_ORDER,
                "strict-reference activities appear out of order",
            )
        )
    deviations.extend(_terminal_deviations(trace, strict=True))
    return tuple(sorted(deviations, key=lambda item: item.deviation_id))


def _terminal_deviations(trace: ProcessTrace, *, strict: bool) -> list[Deviation]:
    terminals = [event for event in trace.events if event.activity in TERMINALS]
    if not terminals:
        return [
            _deviation(
                trace,
                DeviationCategory.MISSING_TERMINAL,
                "trace has no terminal administrative event",
            )
        ]
    deviations = []
    if trace.events[-1].activity not in TERMINALS:
        deviations.append(
            _deviation(
                trace,
                DeviationCategory.EARLY_TERMINATION,
                "a terminal activity is followed by more observed events",
            )
        )
    if strict and terminals[-1].activity != "Referral completed":
        deviations.append(
            _deviation(
                trace,
                DeviationCategory.UNEXPECTED_TERMINAL,
                f"strict reference ends with completion, not {terminals[-1].activity}",
                terminals[-1].activity,
            )
        )
    return deviations


def _governed_deviations(
    trace: ProcessTrace, diagnostic: ReplayDiagnostic
) -> tuple[Deviation, ...]:
    observed = trace.activities
    counts = Counter(observed)
    deviations = []
    for position, activity in enumerate(observed):
        if activity not in GOVERNED_ACTIVITIES:
            deviations.append(
                _deviation(
                    trace,
                    DeviationCategory.UNSUPPORTED_ACTIVITY,
                    f"governed reference does not support {activity}",
                    activity,
                    position,
                )
            )
    for activity, category in (
        ("Referral recategorised", DeviationCategory.UNEXPECTED_RECATEGORISATION),
        ("Clinical team reassigned", DeviationCategory.UNEXPECTED_REASSIGNMENT),
    ):
        if counts[activity] > 1:
            deviations.append(
                _deviation(
                    trace,
                    category,
                    f"{activity} exceeds the governed limit of one",
                    activity,
                )
            )
            deviations.append(
                _deviation(
                    trace,
                    DeviationCategory.EXCESSIVE_LOOP,
                    f"{activity} repeats {counts[activity]} times",
                    activity,
                )
            )
    if counts["Missing information requested"] > 1:
        deviations.append(
            _deviation(
                trace,
                DeviationCategory.EXCESSIVE_LOOP,
                "multiple missing-information request loops are operationally undesirable",
                "Missing information requested",
            )
        )
    if counts["Scheduling failed"]:
        deviations.append(
            _deviation(
                trace,
                DeviationCategory.SCHEDULING_RETRY,
                f"trace contains {counts['Scheduling failed']} failed scheduling attempt(s)",
                "Scheduling failed",
            )
        )
    deviations.extend(_terminal_deviations(trace, strict=False))
    if diagnostic.fitness < 1 and not deviations:
        deviations.append(
            _deviation(
                trace,
                DeviationCategory.UNEXPECTED_ORDER,
                "token replay found ordering or state deviations",
            )
        )
    return tuple(sorted(deviations, key=lambda item: item.deviation_id))


def _status(
    fitness: float | None,
    deviations: tuple[Deviation, ...],
    reference_id: str,
) -> ConformanceStatus:
    if fitness is None:
        return ConformanceStatus.UNAVAILABLE
    governed_nonconforming = any(
        deviation.category not in {DeviationCategory.SCHEDULING_RETRY} for deviation in deviations
    )
    structurally_deviant = (
        bool(deviations) if reference_id == STRICT_REFERENCE_ID else governed_nonconforming
    )
    if fitness == 1 and not structurally_deviant:
        return ConformanceStatus.FULLY_CONFORMING
    if fitness > 0:
        return ConformanceStatus.PARTIALLY_CONFORMING
    return ConformanceStatus.NON_CONFORMING


def _unavailable(trace: ProcessTrace, reference_id: str, warning: str) -> TraceConformanceResult:
    deviation = _deviation(
        trace,
        DeviationCategory.CONFORMANCE_UNAVAILABLE,
        warning,
    )
    return TraceConformanceResult(
        case_id=trace.case_id,
        reference_model=reference_id,
        fitness=None,
        status=ConformanceStatus.UNAVAILABLE,
        alignment_cost=None,
        observed_sequence=trace.activities,
        deviations=(deviation,),
        missing_expected_activities=(),
        unexpected_observed_activities=(),
        warnings=(warning,),
        source_event_ids=tuple(event.event_id for event in trace.events),
    )


def replay_reference(
    process_log: ProcessLog,
    reference_id: str,
    config: ProcessMiningConfig,
    adapter: Pm4pyAdapter,
) -> tuple[TraceConformanceResult, ...]:
    eligible_traces = process_log.traces[: config.maximum_conformance_cases]
    eligible_log = process_log.model_copy(update={"traces": eligible_traces})
    started = monotonic()
    try:
        diagnostics = adapter.replay(eligible_log, reference_id)
    except Pm4pyAdapterError as error:
        return tuple(_unavailable(trace, reference_id, str(error)) for trace in process_log.traces)
    elapsed = monotonic() - started
    by_case = {UUID(diagnostic.case_id): diagnostic for diagnostic in diagnostics}
    results = []
    for trace in process_log.traces:
        diagnostic = by_case.get(trace.case_id)
        if diagnostic is None:
            results.append(
                _unavailable(trace, reference_id, "trace exceeded conformance case limit")
            )
            continue
        deviations = (
            _strict_deviations(trace)
            if reference_id == STRICT_REFERENCE_ID
            else _governed_deviations(trace, diagnostic)
        )
        missing = tuple(
            sorted(
                {
                    deviation.activity
                    for deviation in deviations
                    if deviation.category is DeviationCategory.MISSING_ACTIVITY
                    and deviation.activity is not None
                }
            )
        )
        unexpected = tuple(
            sorted(
                {
                    deviation.activity
                    for deviation in deviations
                    if deviation.category
                    in {
                        DeviationCategory.UNEXPECTED_ACTIVITY,
                        DeviationCategory.UNSUPPORTED_ACTIVITY,
                    }
                    and deviation.activity is not None
                }
            )
        )
        warnings = (
            (f"replay exceeded advisory timeout of {config.conformance_timeout_seconds:g}s",)
            if elapsed > config.conformance_timeout_seconds
            else ()
        )
        results.append(
            TraceConformanceResult(
                case_id=trace.case_id,
                reference_model=reference_id,
                fitness=diagnostic.fitness,
                status=_status(diagnostic.fitness, deviations, reference_id),
                alignment_cost=float(diagnostic.missing_tokens + diagnostic.remaining_tokens),
                observed_sequence=trace.activities,
                deviations=deviations,
                missing_expected_activities=missing,
                unexpected_observed_activities=unexpected,
                warnings=warnings,
                source_event_ids=tuple(event.event_id for event in trace.events),
            )
        )
    return tuple(results)


def _cohorts(
    results: tuple[TraceConformanceResult, ...],
    process_log: ProcessLog,
    dimension: str,
) -> tuple[CohortConformance, ...]:
    trace_by_case = {trace.case_id: trace for trace in process_log.traces}
    grouped: dict[str, list[TraceConformanceResult]] = defaultdict(list)
    for result in results:
        trace = trace_by_case[result.case_id]
        first = trace.events[0]
        value = {
            "terminal_outcome": first.lifecycle_status,
            "referral_source": first.referral_source,
            "service_line": first.service_line,
        }[dimension]
        grouped[value].append(result)
    cohorts = []
    for value, members in sorted(grouped.items()):
        fitness = [result.fitness for result in members if result.fitness is not None]
        cohorts.append(
            CohortConformance(
                dimension=dimension,
                value=value,
                case_count=len(members),
                available_count=len(fitness),
                mean_fitness=fmean(fitness) if fitness else None,
                fully_conforming_rate=(
                    sum(result.status is ConformanceStatus.FULLY_CONFORMING for result in members)
                    / len(fitness)
                    if fitness
                    else None
                ),
            )
        )
    return tuple(cohorts)


def summarize_conformance(
    reference_id: str,
    results: tuple[TraceConformanceResult, ...],
    process_log: ProcessLog,
) -> ConformanceSummary:
    available = [result for result in results if result.fitness is not None]
    fitness = [float(result.fitness) for result in available if result.fitness is not None]
    denominator = len(available)
    deviations = Counter(
        deviation.category.value for result in results for deviation in result.deviations
    )
    return ConformanceSummary(
        reference_model=reference_id,
        case_count=len(results),
        available_count=denominator,
        unavailable_count=len(results) - denominator,
        average_fitness=fmean(fitness) if fitness else None,
        median_fitness=median(fitness) if fitness else None,
        fully_conforming_rate=(
            sum(result.status is ConformanceStatus.FULLY_CONFORMING for result in available)
            / denominator
            if denominator
            else None
        ),
        partially_conforming_rate=(
            sum(result.status is ConformanceStatus.PARTIALLY_CONFORMING for result in available)
            / denominator
            if denominator
            else None
        ),
        non_conforming_rate=(
            sum(result.status is ConformanceStatus.NON_CONFORMING for result in available)
            / denominator
            if denominator
            else None
        ),
        timeout_count=sum(
            any("timeout" in warning for warning in result.warnings) for result in results
        ),
        failure_count=sum(result.status is ConformanceStatus.UNAVAILABLE for result in results),
        by_terminal_outcome=_cohorts(results, process_log, "terminal_outcome"),
        by_referral_source=_cohorts(results, process_log, "referral_source"),
        by_service_line=_cohorts(results, process_log, "service_line"),
        deviation_counts=dict(sorted(deviations.items())),
    )
