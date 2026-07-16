"""Deterministic aggregation of case metrics into operational cohorts."""

from collections.abc import Callable, Iterable
from statistics import fmean, median

from workflowtwin.analytics.config import AnalysisConfig, CohortDimension
from workflowtwin.analytics.models import (
    CaseMetrics,
    CohortMetrics,
    MetricName,
    MetricStatus,
    RateMetric,
    SummaryMetric,
)

TERMINAL_STATUSES = {"completed", "cancelled", "rejected", "closed_other"}
SUMMARY_METRICS = (
    MetricName.CASE_DURATION,
    MetricName.WAITING_TIME,
    MetricName.PROCESSING_TIME,
    MetricName.MANUAL_TOUCHES,
    MetricName.HANDOFFS,
    MetricName.REWORK_COUNT,
    MetricName.TIME_TO_FIRST_CHECK,
    MetricName.TIME_TO_BOOKING,
    MetricName.ASSIGNMENT_WAIT,
    MetricName.FAILED_SCHEDULING,
    MetricName.REASSIGNMENTS,
    MetricName.MAX_INGESTION_DELAY,
)
SUMMARY_STATUSES = {MetricStatus.CALCULATED, MetricStatus.ESTIMATED}


def _rate(numerator: int, denominator: int) -> RateMetric:
    return RateMetric(
        numerator=numerator,
        denominator=denominator,
        value=numerator / denominator if denominator else None,
    )


def _is_positive_number(value: float | int | bool | None) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _summary(
    cases: tuple[CaseMetrics, ...], metric_name: MetricName, config: AnalysisConfig
) -> SummaryMetric:
    values = [
        float(result.value)
        for case in cases
        if (result := case.metrics[metric_name]).status in SUMMARY_STATUSES
        and result.value is not None
        and not isinstance(result.value, bool)
    ]
    return SummaryMetric(
        available_count=len(values),
        excluded_count=len(cases) - len(values),
        mean=fmean(values) if values else None,
        median=median(values) if values else None,
        percentiles={
            f"p{quantile * 100:g}": _percentile(values, quantile) for quantile in config.percentiles
        }
        if values
        else {},
    )


def _aggregate(
    dimension: str,
    value: str,
    cases: tuple[CaseMetrics, ...],
    config: AnalysisConfig,
) -> CohortMetrics:
    terminal_count = sum(case.lifecycle_status in TERMINAL_STATUSES for case in cases)
    open_count = len(cases) - terminal_count
    completed = sum(case.lifecycle_status == "completed" for case in cases)
    cancelled = sum(case.lifecycle_status == "cancelled" for case in cases)
    rejected = sum(case.lifecycle_status == "rejected" for case in cases)
    stuck_results = [
        case.metrics[MetricName.IS_STUCK]
        for case in cases
        if case.metrics[MetricName.IS_STUCK].value is not None
    ]
    stuck = sum(result.value is True for result in stuck_results)
    first_pass_results = [
        case.metrics[MetricName.FIRST_PASS_COMPLETE]
        for case in cases
        if case.metrics[MetricName.FIRST_PASS_COMPLETE].value is not None
    ]
    delayed = sum(
        _is_positive_number(case.metrics[MetricName.DELAYED_EVENTS].value) for case in cases
    )
    out_of_order = sum(
        case.metrics[MetricName.OUT_OF_ORDER_INGESTION].value is True for case in cases
    )
    available_results = sum(
        result.status in {MetricStatus.CALCULATED, MetricStatus.ESTIMATED, MetricStatus.PARTIAL}
        for case in cases
        for result in case.metrics.values()
    )
    result_count = sum(len(case.metrics) for case in cases)
    return CohortMetrics(
        dimension=dimension,
        value=value,
        case_count=len(cases),
        completed_count=completed,
        cancellation_count=cancelled,
        rejection_count=rejected,
        stuck_count=stuck,
        rates={
            "completion_rate": _rate(completed, terminal_count),
            "cancellation_rate": _rate(cancelled, terminal_count),
            "rejection_rate": _rate(rejected, terminal_count),
            "stuck_case_rate": _rate(stuck, open_count),
            "first_pass_completeness_rate": _rate(
                sum(result.value is True for result in first_pass_results),
                len(first_pass_results),
            ),
            "delayed_ingestion_rate": _rate(delayed, len(cases)),
            "out_of_order_ingestion_rate": _rate(out_of_order, len(cases)),
            "metric_availability_rate": _rate(available_results, result_count),
        },
        summaries={
            metric_name.value: _summary(cases, metric_name, config)
            for metric_name in SUMMARY_METRICS
        },
        eligible_for_comparison=len(cases) >= config.minimum_cohort_size,
    )


def _dimension_value(
    dimension: CohortDimension,
) -> Callable[[CaseMetrics], str | None]:
    if dimension is CohortDimension.REFERRAL_SOURCE:
        return lambda case: case.referral_source
    if dimension is CohortDimension.SERVICE_LINE:
        return lambda case: case.service_line
    if dimension is CohortDimension.SOURCE_SYSTEM:
        return lambda case: case.primary_source_system
    if dimension is CohortDimension.ASSIGNED_TEAM:
        return lambda case: case.assigned_team
    return lambda case: case.lifecycle_status


def aggregate_cohorts(
    cases: Iterable[CaseMetrics], config: AnalysisConfig
) -> tuple[CohortMetrics, tuple[CohortMetrics, ...]]:
    """Return the overall metrics and stable configured cohort breakdowns."""
    all_cases = tuple(sorted(cases, key=lambda case: case.case_id.hex))
    overall = _aggregate("overall", "all", all_cases, config)
    cohorts = []
    for dimension in config.cohort_dimensions:
        value_for = _dimension_value(dimension)
        values = sorted({value for case in all_cases if (value := value_for(case)) is not None})
        for value in values:
            members = tuple(case for case in all_cases if value_for(case) == value)
            cohorts.append(_aggregate(dimension.value, value, members, config))
    return overall, tuple(cohorts)
