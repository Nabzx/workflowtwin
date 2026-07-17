"""Typed metric, process, and burden comparisons for simulated datasets."""

from workflowtwin.analytics.models import BaselineAnalysis, CohortMetrics, MetricStatus
from workflowtwin.opportunities.models import OpportunityCandidate
from workflowtwin.process_mining.models import ProcessMiningAnalysis
from workflowtwin.simulation.config import SimulationConfig
from workflowtwin.simulation.models import (
    AnalysisSummary,
    BurdenComparison,
    CaseSimulationResult,
    EffectClassification,
    MetricComparison,
    PolicyDecisionStatus,
    ProcessComparison,
    ProcessSummary,
)

SUMMARY_EFFECTS = {
    "manual_touches": EffectClassification.INTENDED_DIRECT,
    "rework_count": EffectClassification.INTENDED_DIRECT,
    "time_to_first_completeness_check_hours": EffectClassification.INTENDED_DIRECT,
    "case_duration_hours": EffectClassification.SECONDARY,
    "waiting_time_business_hours": EffectClassification.SECONDARY,
    "handoffs": EffectClassification.UNCHANGED,
    "failed_scheduling_attempts": EffectClassification.UNCHANGED,
}


def _cohort(analysis: BaselineAnalysis, dimension: str, value: str) -> CohortMetrics:
    return next(
        item for item in analysis.cohorts if item.dimension == dimension and item.value == value
    )


def _difference(
    baseline: float | None, simulated: float | None
) -> tuple[float | None, float | None]:
    if baseline is None or simulated is None:
        return None, None
    absolute = simulated - baseline
    relative = absolute / baseline if baseline != 0 else None
    return absolute, relative


def compare_metrics(
    baseline: BaselineAnalysis,
    simulated: BaselineAnalysis,
    candidate: OpportunityCandidate,
) -> tuple[MetricComparison, ...]:
    source = _cohort(baseline, candidate.cohort_dimension, candidate.cohort_value)
    counterfactual = _cohort(simulated, candidate.cohort_dimension, candidate.cohort_value)
    comparisons: list[MetricComparison] = []
    first_pass_source = source.rates["first_pass_completeness_rate"]
    first_pass_simulated = counterfactual.rates["first_pass_completeness_rate"]
    absolute, relative = _difference(first_pass_source.value, first_pass_simulated.value)
    comparisons.append(
        MetricComparison(
            metric_name="first_pass_completeness_rate",
            baseline_value=first_pass_source.value,
            simulated_value=first_pass_simulated.value,
            absolute_difference=absolute,
            relative_difference=relative,
            unit="rate",
            denominator=first_pass_simulated.denominator,
            cohort_dimension=candidate.cohort_dimension,
            cohort_value=candidate.cohort_value,
            status=(MetricStatus.CALCULATED if absolute is not None else MetricStatus.UNAVAILABLE),
            effect_classification=EffectClassification.UNCHANGED,
            interpretation=(
                "The intervention validates existing structured information; it does not "
                "invent missing information, so first-pass completeness is not targeted."
            ),
            warnings=(),
        )
    )
    for metric_name, classification in SUMMARY_EFFECTS.items():
        source_metric = source.summaries[metric_name]
        simulated_metric = counterfactual.summaries[metric_name]
        absolute, relative = _difference(source_metric.mean, simulated_metric.mean)
        comparisons.append(
            MetricComparison(
                metric_name=metric_name,
                baseline_value=source_metric.mean,
                simulated_value=simulated_metric.mean,
                absolute_difference=absolute,
                relative_difference=relative,
                unit=(
                    "count_per_case"
                    if metric_name
                    in {"manual_touches", "rework_count", "handoffs", "failed_scheduling_attempts"}
                    else "hours"
                ),
                denominator=simulated_metric.available_count,
                cohort_dimension=candidate.cohort_dimension,
                cohort_value=candidate.cohort_value,
                status=(
                    MetricStatus.CALCULATED if absolute is not None else MetricStatus.UNAVAILABLE
                ),
                effect_classification=classification,
                interpretation=(
                    "Simulated by applying event-history rules and recalculating the "
                    "existing metric."
                ),
                warnings=(
                    ("relative difference unavailable because baseline is zero",)
                    if absolute is not None and relative is None
                    else ()
                ),
            )
        )
    return tuple(comparisons)


def summarize_baseline(
    analysis: BaselineAnalysis, candidate: OpportunityCandidate
) -> AnalysisSummary:
    cohort = _cohort(analysis, candidate.cohort_dimension, candidate.cohort_value)
    metrics: dict[str, float | int | None] = {
        name: value.mean for name, value in cohort.summaries.items()
    }
    metrics.update({name: value.value for name, value in cohort.rates.items()})
    return AnalysisSummary(
        analysis_fingerprint=analysis.analysis_fingerprint,
        case_count=analysis.case_count,
        event_count=analysis.event_count,
        cohort_dimension=candidate.cohort_dimension,
        cohort_value=candidate.cohort_value,
        metrics=dict(sorted(metrics.items())),
        warning_count=len(analysis.warnings) + len(analysis.quality.data_validation_warnings),
    )


def summarize_process(analysis: ProcessMiningAnalysis) -> ProcessSummary:
    complexity = analysis.complexity
    return ProcessSummary(
        process_analysis_fingerprint=analysis.process_analysis_fingerprint,
        activity_count=len(analysis.activity_statistics),
        transition_count=len(analysis.transition_statistics),
        variant_count=len(analysis.variants),
        governed_fully_conforming_rate=(
            analysis.governed_conformance.fully_conforming_rate
            if analysis.governed_conformance
            else None
        ),
        strict_fully_conforming_rate=(
            analysis.strict_conformance.fully_conforming_rate
            if analysis.strict_conformance
            else None
        ),
        bottleneck_candidate_count=len(analysis.bottleneck_candidates),
        complexity={
            "loop_case_rate": complexity.loop_case_rate,
            "rework_case_rate": complexity.rework_case_rate,
            "handoff_case_rate": complexity.handoff_case_rate,
            "variant_entropy_bits": complexity.variant_entropy_bits,
            "top_5_variant_coverage": complexity.top_5_variant_coverage,
        },
    )


def compare_process(
    baseline: ProcessMiningAnalysis, simulated: ProcessMiningAnalysis
) -> tuple[ProcessComparison, ...]:
    values: tuple[tuple[str, float | int | None, float | int | None], ...] = (
        ("variant_count", len(baseline.variants), len(simulated.variants)),
        ("loop_case_rate", baseline.complexity.loop_case_rate, simulated.complexity.loop_case_rate),
        (
            "rework_case_rate",
            baseline.complexity.rework_case_rate,
            simulated.complexity.rework_case_rate,
        ),
        (
            "variant_entropy_bits",
            baseline.complexity.variant_entropy_bits,
            simulated.complexity.variant_entropy_bits,
        ),
        (
            "governed_fully_conforming_rate",
            baseline.governed_conformance.fully_conforming_rate
            if baseline.governed_conformance
            else None,
            simulated.governed_conformance.fully_conforming_rate
            if simulated.governed_conformance
            else None,
        ),
        (
            "bottleneck_candidate_count",
            len(baseline.bottleneck_candidates),
            len(simulated.bottleneck_candidates),
        ),
    )
    results = []
    for name, source, counterfactual in values:
        absolute = (
            float(counterfactual) - float(source)
            if source is not None and counterfactual is not None
            else None
        )
        results.append(
            ProcessComparison(
                metric_name=name,
                baseline_value=source,
                simulated_value=counterfactual,
                absolute_difference=absolute,
                interpretation=(
                    "Descriptive counterfactual process difference; not a causal estimate."
                ),
                warnings=(),
            )
        )
    return tuple(results)


def compare_burden(
    baseline: BaselineAnalysis,
    simulated: BaselineAnalysis,
    candidate: OpportunityCandidate,
    case_results: tuple[CaseSimulationResult, ...],
    config: SimulationConfig,
) -> BurdenComparison:
    source = _cohort(baseline, candidate.cohort_dimension, candidate.cohort_value)
    counterfactual = _cohort(simulated, candidate.cohort_dimension, candidate.cohort_value)
    source_mean = source.summaries["manual_touches"].mean or 0.0
    simulated_mean = counterfactual.summaries["manual_touches"].mean or 0.0
    touch_hours = config.manual_touch_minutes_proxy / 60
    baseline_hours = source_mean * source.case_count * touch_hours
    simulated_hours = simulated_mean * counterfactual.case_count * touch_hours
    review_touches = sum(
        result.decision.manual_touch_overhead
        for result in case_results
        if result.decision.status
        in {
            PolicyDecisionStatus.APPROVED_SIMULATED_ACTION,
            PolicyDecisionStatus.REJECTED_BY_REVIEWER,
        }
    )
    fallback_touches = sum(
        result.decision.manual_touch_overhead
        for result in case_results
        if result.decision.status
        in {
            PolicyDecisionStatus.FALLBACK_TO_MANUAL,
            PolicyDecisionStatus.SIMULATION_FAILURE,
        }
    )
    rollback_touches = sum(
        result.decision.manual_touch_overhead
        for result in case_results
        if result.decision.status is PolicyDecisionStatus.ROLLED_BACK
    )
    review_hours = review_touches * touch_hours
    fallback_hours = fallback_touches * touch_hours
    recovery_hours = rollback_touches * touch_hours
    operating_hours = review_hours + fallback_hours + recovery_hours
    gross = baseline_hours - simulated_hours
    net = gross - operating_hours
    upper = candidate.observed_burden.estimated_manual_touch_hours or 0.0
    warnings = []
    if net > upper:
        warnings.append("simulated net difference exceeds the observed addressable upper bound")
    cost = config.administrative_cost_per_hour_gbp
    return BurdenComparison(
        baseline_manual_touch_hours=baseline_hours,
        simulated_workflow_touch_hours=simulated_hours,
        review_overhead_hours=review_hours,
        fallback_overhead_hours=fallback_hours,
        failure_recovery_hours=recovery_hours,
        simulated_operating_burden_hours=operating_hours,
        gross_simulated_difference_hours=gross,
        net_simulated_difference_hours=net,
        addressable_upper_bound_hours=upper,
        upper_bound_proportion_modelled=net / upper if upper else None,
        baseline_associated_cost_gbp=baseline_hours * cost,
        simulated_associated_cost_gbp=simulated_hours * cost,
        simulated_operating_cost_gbp=operating_hours * cost,
        simulated_net_cost_difference_gbp=net * cost,
        assumptions=(
            f"each workflow or control touch proxies {config.manual_touch_minutes_proxy:g} minutes",
            f"fictional administrative cost proxy is GBP {cost:g} per hour",
            "review queue delay is elapsed time, not staff labour",
            "cost differences are simulated and are not realised savings or ROI",
        ),
        warnings=tuple(warnings),
    )
