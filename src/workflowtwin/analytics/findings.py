"""Transparent materiality rules for fictional operational baseline findings."""

from dataclasses import dataclass

from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.models import (
    BaselineFinding,
    CaseMetrics,
    CohortMetrics,
    Materiality,
    MetricName,
)


@dataclass(frozen=True, slots=True)
class FindingRule:
    finding_type: str
    metric_name: str
    direction: str
    dimensions: tuple[str, ...]
    is_rate: bool = False


RULES = (
    FindingRule(
        "lower_first_pass_completeness",
        "first_pass_completeness_rate",
        "lower",
        ("referral_source",),
        True,
    ),
    FindingRule(
        "longer_assignment_wait",
        MetricName.ASSIGNMENT_WAIT.value,
        "higher",
        ("service_line",),
    ),
    FindingRule(
        "longer_booking_time",
        MetricName.TIME_TO_BOOKING.value,
        "higher",
        ("service_line",),
    ),
    FindingRule(
        "elevated_failed_scheduling",
        MetricName.FAILED_SCHEDULING.value,
        "higher",
        ("service_line",),
    ),
    FindingRule(
        "elevated_rework",
        MetricName.REWORK_COUNT.value,
        "higher",
        ("referral_source", "service_line"),
    ),
    FindingRule(
        "elevated_reassignment",
        MetricName.REASSIGNMENTS.value,
        "higher",
        ("service_line",),
    ),
    FindingRule(
        "elevated_handoffs",
        MetricName.HANDOFFS.value,
        "higher",
        ("service_line",),
    ),
    FindingRule(
        "longer_case_duration",
        MetricName.CASE_DURATION.value,
        "higher",
        ("referral_source", "service_line"),
    ),
    FindingRule(
        "elevated_stuck_rate",
        "stuck_case_rate",
        "higher",
        ("referral_source", "service_line"),
        True,
    ),
    FindingRule(
        "elevated_delayed_ingestion",
        "delayed_ingestion_rate",
        "higher",
        ("source_system",),
        True,
    ),
)


def _cohort_value(cohort: CohortMetrics, rule: FindingRule) -> float | None:
    if rule.is_rate:
        return cohort.rates[rule.metric_name].value
    return cohort.summaries[rule.metric_name].mean


def _case_in_cohort(case: CaseMetrics, cohort: CohortMetrics) -> bool:
    values = {
        "referral_source": case.referral_source,
        "service_line": case.service_line,
        "source_system": case.primary_source_system,
        "assigned_team": case.assigned_team,
        "terminal_outcome": case.lifecycle_status,
    }
    return values.get(cohort.dimension) == cohort.value


def _supports(case: CaseMetrics, rule: FindingRule, baseline: float) -> bool:
    if rule.metric_name == "first_pass_completeness_rate":
        return case.metrics[MetricName.FIRST_PASS_COMPLETE].value is False
    if rule.metric_name == "stuck_case_rate":
        return case.metrics[MetricName.IS_STUCK].value is True
    if rule.metric_name == "delayed_ingestion_rate":
        value = case.metrics[MetricName.DELAYED_EVENTS].value
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
    value = case.metrics[MetricName(rule.metric_name)].value
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    return value > baseline if rule.direction == "higher" else value < baseline


def detect_findings(
    overall: CohortMetrics,
    cohorts: tuple[CohortMetrics, ...],
    case_metrics: tuple[CaseMetrics, ...],
    config: AnalysisConfig,
) -> tuple[BaselineFinding, ...]:
    """Compare eligible cohorts with the overall baseline using documented rules."""
    findings = []
    for rule in RULES:
        baseline = _cohort_value(overall, rule)
        if baseline is None:
            continue
        for cohort in cohorts:
            if cohort.dimension not in rule.dimensions or not cohort.eligible_for_comparison:
                continue
            observed = _cohort_value(cohort, rule)
            if observed is None:
                continue
            absolute = observed - baseline
            directional = absolute if rule.direction == "higher" else -absolute
            relative = absolute / baseline if baseline else None
            relative_directional = (
                relative
                if rule.direction == "higher"
                else -relative
                if relative is not None
                else None
            )
            threshold_met = (
                directional >= config.absolute_rate_materiality_threshold
                if rule.is_rate
                else relative_directional is not None
                and relative_directional >= config.relative_materiality_threshold
            )
            if not threshold_met:
                continue
            strength = (
                Materiality.STRONG
                if (
                    directional >= config.absolute_rate_materiality_threshold * 2
                    if rule.is_rate
                    else relative_directional is not None
                    and relative_directional >= config.relative_materiality_threshold * 2
                )
                else Materiality.MATERIAL
            )
            supporting_ids = tuple(
                case.case_id
                for case in case_metrics
                if _case_in_cohort(case, cohort) and _supports(case, rule, baseline)
            )[:25]
            finding_id = "-".join((cohort.dimension, cohort.value, rule.finding_type)).replace(
                "_", "-"
            )
            findings.append(
                BaselineFinding(
                    finding_id=finding_id,
                    finding_type=rule.finding_type,
                    cohort_dimension=cohort.dimension,
                    cohort_value=cohort.value,
                    comparison="overall eligible population",
                    metric_name=rule.metric_name,
                    observed_value=observed,
                    baseline_value=baseline,
                    absolute_difference=absolute,
                    relative_difference=relative,
                    cohort_size=cohort.case_count,
                    baseline_size=overall.case_count,
                    materiality=strength,
                    supporting_case_ids=supporting_ids,
                    caveats=(
                        "descriptive materiality rule; no statistical significance claim",
                        "fictional administrative workflow data only",
                    ),
                    minimum_cohort_size_met=True,
                )
            )
    return tuple(sorted(findings, key=lambda finding: finding.finding_id))
