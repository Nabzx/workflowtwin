"""Post-simulation benchmark checks that never influence policy decisions."""

from workflowtwin.simulation.models import (
    PrototypeDecision,
    ScenarioResult,
    SimulationBenchmarkEvaluation,
)


def evaluate_simulation(
    scenario: ScenarioResult,
    decision: PrototypeDecision,
    *,
    expected_opportunity_id: str,
) -> SimulationBenchmarkEvaluation:
    manifest = scenario.manifest
    checks = {
        "correct_opportunity_selected": manifest.selected_opportunity_id == expected_opportunity_id,
        "only_eligible_cases_affected": all(
            result.eligibility.eligible for result in scenario.case_results if result.event_changes
        ),
        "source_events_unchanged": scenario.quality.source_events_unchanged,
        "counterfactual_valid": scenario.quality.is_valid,
        "human_review_represented": manifest.review_required_count > 0,
        "failures_or_fallbacks_represented": (
            manifest.intervention_failure_count + manifest.fallback_count > 0
        ),
        "simulated_difference_within_upper_bound": (
            scenario.burden_comparison.net_simulated_difference_hours
            <= scenario.burden_comparison.addressable_upper_bound_hours
        ),
        "stable_fingerprints_present": bool(
            scenario.scenario_fingerprint
            and scenario.counterfactual_baseline_fingerprint
            and scenario.counterfactual_process_fingerprint
        ),
        "decision_is_not_deployment_approval": decision.status.value != "approved_for_deployment",
    }
    return SimulationBenchmarkEvaluation(
        checks=checks,
        passed_count=sum(checks.values()),
        check_count=len(checks),
        notes=(
            "benchmark checks run only after decisions and counterfactual outputs exist",
            "historical path truth remains isolated from intervention policy",
        ),
    )
