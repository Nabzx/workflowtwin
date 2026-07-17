"""Observed administrative burden without benefit or savings forecasts."""

from workflowtwin.analytics.models import CohortMetrics
from workflowtwin.opportunities.config import AnnualisationPolicy, OpportunityConfig
from workflowtwin.opportunities.models import (
    ObservedBurden,
    OpportunityAnalysisInput,
    OpportunityArchetypeId,
)
from workflowtwin.opportunities.rules import OpportunitySeed

CANDIDATE_TYPES = {
    OpportunityArchetypeId.INTAKE_COMPLETENESS: "referral_source_rework_path",
    OpportunityArchetypeId.ASSIGNMENT_ROUTING: "service_line_assignment_delay",
    OpportunityArchetypeId.SCHEDULING_COORDINATION: "service_line_scheduling_retries",
    OpportunityArchetypeId.HANDOFF_REDUCTION: "service_line_reassignment",
}


def _cohort(analysis_input: OpportunityAnalysisInput, seed: OpportunitySeed) -> CohortMetrics:
    if seed.cohort_dimension == "overall":
        return analysis_input.baseline.overall
    return next(
        (
            item
            for item in analysis_input.baseline.cohorts
            if item.dimension == seed.cohort_dimension
            and item.value == seed.cohort_value
        ),
        analysis_input.baseline.overall,
    )


def _summary_value(cohort: CohortMetrics, metric: str) -> float | None:
    summary = cohort.summaries.get(metric)
    return summary.mean if summary is not None else None


def calculate_observed_burden(
    analysis_input: OpportunityAnalysisInput,
    seed: OpportunitySeed,
    config: OpportunityConfig,
) -> ObservedBurden:
    cohort = _cohort(analysis_input, seed)
    process = analysis_input.process
    process_candidate = next(
        (
            item
            for item in process.bottleneck_candidates
            if item.candidate_type == CANDIDATE_TYPES.get(seed.archetype)
            and item.cohort_dimension == seed.cohort_dimension
            and item.cohort_value == seed.cohort_value
        ),
        None,
    )
    if seed.archetype is OpportunityArchetypeId.STUCK_CASE_MONITORING:
        affected = int(process.deviation_summary.get("missing_terminal_event", 0))
    elif seed.archetype is OpportunityArchetypeId.DATA_QUALITY_MONITORING:
        affected = max(
            analysis_input.baseline.quality.delayed_ingestion_cases,
            analysis_input.baseline.quality.out_of_order_ingestion_cases,
        )
    elif process_candidate is not None:
        affected = min(process_candidate.frequency, process_candidate.case_count)
    else:
        affected = None
    affected_rate = (
        affected / cohort.case_count if affected is not None and cohort.case_count else None
    )
    annualisation_factor = 1.0
    period_normalised = float(affected) if affected is not None else None
    if config.annualisation_policy is AnnualisationPolicy.REPORTING_PERIOD:
        start = analysis_input.baseline.reporting_period_start
        end = analysis_input.baseline.reporting_period_end
        if start is not None and end is not None and end > start:
            annualisation_factor = 365.0 / ((end - start).total_seconds() / 86_400)
            period_normalised = affected * annualisation_factor if affected is not None else None
    manual_touches_per_case = _summary_value(cohort, "manual_touches")
    observed_manual_touches = (
        manual_touches_per_case * affected
        if manual_touches_per_case is not None and affected is not None
        else None
    )
    manual_hours = (
        observed_manual_touches * config.manual_touch_minutes_proxy / 60
        if observed_manual_touches is not None
        else None
    )
    admin_cost = (
        manual_hours * config.administrative_cost_per_hour_gbp if manual_hours is not None else None
    )
    rework = (
        process_candidate.frequency
        if process_candidate is not None
        and seed.archetype
        in {
            OpportunityArchetypeId.INTAKE_COMPLETENESS,
            OpportunityArchetypeId.SCHEDULING_COORDINATION,
            OpportunityArchetypeId.HANDOFF_REDUCTION,
        }
        else None
    )
    handoff_mean = _summary_value(cohort, "handoffs")
    handoffs = (
        handoff_mean * affected if handoff_mean is not None and affected is not None else None
    )
    elapsed = process_candidate.elapsed_hours.median if process_candidate is not None else None
    return ObservedBurden(
        affected_case_count=affected,
        affected_case_rate=affected_rate,
        period_normalised_cases=period_normalised,
        observed_manual_touches=observed_manual_touches,
        estimated_manual_touch_hours=manual_hours,
        rework_events=rework,
        handoffs=handoffs,
        elapsed_delay_hours=elapsed,
        business_delay_hours=None,
        stuck_case_count=(
            affected if seed.archetype is OpportunityArchetypeId.STUCK_CASE_MONITORING else None
        ),
        associated_admin_cost_gbp=admin_cost,
        addressable_upper_bound_gbp=admin_cost,
        expected_benefit_gbp=None,
        assumptions=(
            f"each recorded manual touch proxies "
            f"{config.manual_touch_minutes_proxy:g} staff minutes",
            f"administrative staff cost proxy is GBP "
            f"{config.administrative_cost_per_hour_gbp:g} per hour",
            f"period normalisation policy is {config.annualisation_policy.value}",
            "addressable upper bound is current associated burden, not removable burden "
            "or a forecast",
        ),
        warnings=(
            "elapsed delay is not active work and is not assumed removable",
            "affected counts can represent associated occurrences rather than unique causal cases",
        ),
    )
