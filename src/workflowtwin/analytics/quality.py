"""Coverage and data-quality reporting for baseline analysis."""

from collections import Counter

from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.models import AnalysisQuality, CaseMetrics, MetricName
from workflowtwin.analytics.timelines import CaseTimeline, TimelineBuildResult
from workflowtwin.domain.referrals.enums import EventType


def build_quality_report(
    *,
    cases_received: int,
    timeline_result: TimelineBuildResult,
    analysed_timelines: tuple[CaseTimeline, ...],
    case_metrics: tuple[CaseMetrics, ...],
    config: AnalysisConfig,
) -> AnalysisQuality:
    """Summarise exclusions, ambiguity, latency, and per-metric status coverage."""
    analysed_ids = {timeline.referral_case.id for timeline in analysed_timelines}
    missing: Counter[str] = Counter()
    for timeline in analysed_timelines:
        event_types = {event.event_type for event in timeline.events}
        if EventType.REFERRAL_RECEIVED not in event_types:
            missing[EventType.REFERRAL_RECEIVED.value] += 1
        if EventType.COMPLETENESS_CHECK_COMPLETED not in event_types:
            missing[EventType.COMPLETENESS_CHECK_COMPLETED.value] += 1
        if timeline.referral_case.closed_at is not None and not event_types.intersection(
            {
                EventType.REFERRAL_COMPLETED,
                EventType.REFERRAL_CANCELLED,
                EventType.REFERRAL_REJECTED,
                EventType.REFERRAL_CLOSED_OTHER,
            }
        ):
            missing["terminal_event"] += 1
    status_counts: dict[str, dict[str, int]] = {}
    for metric_name in MetricName:
        counts = Counter(
            case.metrics[metric_name].status.value
            for case in case_metrics
            if metric_name in case.metrics
        )
        status_counts[metric_name.value] = dict(sorted(counts.items()))
    unsupported = sum(not timeline.supported_schema for timeline in timeline_result.timelines)
    metrics_by_case = {case.case_id: case for case in case_metrics}
    ambiguous = sum(
        bool(timeline.excluded_duplicate_event_ids)
        or "multiple terminal events; first event-time terminal used"
        in metrics_by_case[timeline.referral_case.id].metrics[MetricName.CASE_DURATION].warnings
        for timeline in analysed_timelines
    )
    delayed = sum(
        int(case.metrics[MetricName.DELAYED_EVENTS].value or 0) > 0 for case in case_metrics
    )
    out_of_order = sum(
        case.metrics[MetricName.OUT_OF_ORDER_INGESTION].value is True for case in case_metrics
    )
    data_warnings = sorted(
        {warning for timeline in timeline_result.timelines for warning in timeline.warnings}
    )
    configuration_warnings = [
        "processing time is a manual-touch proxy, not observed staff effort",
        "waiting and stuck metrics depend on the configured business calendar and cutoff",
        "comparative findings are materiality rules and do not claim statistical significance",
    ]
    if any(
        timeline.assigned_team is None
        for timeline in analysed_timelines
        if timeline.referral_case.id in analysed_ids
    ):
        configuration_warnings.append(
            "assigned-team cohorts exclude cases without structured assignment metadata"
        )
    return AnalysisQuality(
        cases_received=cases_received,
        cases_analysed=len(case_metrics),
        cases_excluded_entirely=cases_received - len(case_metrics),
        unsupported_schema_cases=unsupported,
        orphan_event_count=timeline_result.orphan_event_count,
        ambiguous_timeline_cases=ambiguous,
        identical_timestamp_cases=sum(
            timeline.identical_event_timestamps for timeline in analysed_timelines
        ),
        delayed_ingestion_cases=delayed,
        out_of_order_ingestion_cases=out_of_order,
        missing_required_event_counts=dict(sorted(missing.items())),
        metric_status_counts=status_counts,
        data_validation_warnings=tuple(data_warnings),
        configuration_warnings=tuple(configuration_warnings),
    )
