"""Frontend-independent metric, process, scenario, and sensitivity datasets."""

from workflowtwin.simulation.models import (
    ScenarioResult,
    SensitivityResult,
    SimulationGraphData,
)


def build_graph_data(
    scenario: ScenarioResult,
    sensitivity: tuple[SensitivityResult, ...],
) -> SimulationGraphData:
    return SimulationGraphData(
        metric_comparison=tuple(
            {
                "metric": item.metric_name,
                "baseline_value": item.baseline_value,
                "scenario_value": item.simulated_value,
                "unit": item.unit,
                "cohort": item.cohort_value,
                "status": item.status.value,
                "classification": item.effect_classification.value,
            }
            for item in scenario.metric_comparisons
        ),
        process_comparison=tuple(
            {
                "metric": item.metric_name,
                "baseline_value": item.baseline_value,
                "scenario_value": item.simulated_value,
                "difference": item.absolute_difference,
            }
            for item in scenario.process_comparisons
        ),
        scenario_comparison=(
            {
                "scenario": scenario.scenario_id,
                "affected_cases": scenario.manifest.affected_case_count,
                "control_overhead_hours": (
                    scenario.burden_comparison.simulated_operating_burden_hours
                ),
                "net_burden_difference_hours": (
                    scenario.burden_comparison.net_simulated_difference_hours
                ),
                "failures": scenario.manifest.intervention_failure_count,
                "fallbacks": scenario.manifest.fallback_count,
            },
        ),
        sensitivity=tuple(
            {
                "parameter": item.parameter,
                "tested_value": item.tested_value,
                "key_outcome": item.net_burden_difference_hours,
                "threshold_crossed": item.conclusion_changed,
            }
            for item in sensitivity
        ),
    )
