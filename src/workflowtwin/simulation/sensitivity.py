"""Small one-at-a-time sensitivity and modelled break-even analysis."""

from workflowtwin.simulation.analysis import analyze_counterfactual_baseline
from workflowtwin.simulation.comparisons import compare_burden, compare_metrics
from workflowtwin.simulation.config import SimulationConfig
from workflowtwin.simulation.counterfactuals import CounterfactualSimulator
from workflowtwin.simulation.fingerprint import stable_hash
from workflowtwin.simulation.models import (
    InterventionDefinition,
    SensitivityResult,
    SimulationInput,
    ThresholdResult,
)


def _run_value(
    simulation_input: SimulationInput,
    definition: InterventionDefinition,
    config: SimulationConfig,
    parameter: str,
    value: float,
) -> tuple[float, float, float | None, str]:
    parameters = config.parameters
    if parameter == "review_turnaround_max_hours":
        updated = parameters.model_copy(
            update={
                "human_review_turnaround_hours": (
                    parameters.human_review_turnaround_hours[0],
                    value,
                )
            }
        )
    else:
        updated = parameters.model_copy(update={parameter: value})
    run_config = config.model_copy(update={"parameters": updated})
    counterfactual = CounterfactualSimulator(run_config).simulate(simulation_input, definition)
    baseline = analyze_counterfactual_baseline(simulation_input, counterfactual).baseline
    candidate = next(
        item
        for item in simulation_input.opportunities.candidates
        if item.opportunity_id == definition.source_opportunity_id
    )
    burden = compare_burden(
        simulation_input.baseline,
        baseline,
        candidate,
        counterfactual.case_results,
        run_config,
    )
    comparisons = compare_metrics(simulation_input.baseline, baseline, candidate)
    target = next(item for item in comparisons if item.metric_name == "manual_touches")
    fingerprint = stable_hash(
        {
            "parameter": parameter,
            "value": value,
            "manifest": counterfactual.manifest,
            "burden": burden,
        }
    )
    return (
        burden.net_simulated_difference_hours,
        burden.simulated_operating_burden_hours,
        target.absolute_difference,
        fingerprint,
    )


def run_sensitivity(
    simulation_input: SimulationInput,
    definition: InterventionDefinition,
    config: SimulationConfig,
    central_net_burden_difference: float,
) -> tuple[SensitivityResult, ...]:
    base_positive = central_net_burden_difference > 0
    tests = (
        ("effectiveness", config.parameters.effectiveness, (0.50, 0.85)),
        ("false_positive_rate", config.parameters.false_positive_rate, (0.02, 0.20)),
        ("manual_fallback_rate", config.parameters.manual_fallback_rate, (0.05, 0.25)),
        (
            "review_turnaround_max_hours",
            config.parameters.human_review_turnaround_hours[1],
            (1.0, 8.0),
        ),
    )
    results = []
    for parameter, baseline_value, values in tests:
        for value in values:
            net, overhead, target, fingerprint = _run_value(
                simulation_input, definition, config, parameter, value
            )
            results.append(
                SensitivityResult(
                    parameter=parameter,
                    baseline_value=baseline_value,
                    tested_value=value,
                    target_metric_difference=target,
                    net_burden_difference_hours=net,
                    control_overhead_hours=overhead,
                    conclusion_changed=(net > 0) != base_positive,
                    scenario_fingerprint=fingerprint,
                )
            )
    return tuple(results)


def run_threshold_analysis(
    simulation_input: SimulationInput,
    definition: InterventionDefinition,
    config: SimulationConfig,
) -> tuple[ThresholdResult, ...]:
    tests = {
        "false_positive_rate": (0.02, 0.10, 0.20, 0.30, 0.40),
        "manual_fallback_rate": (0.05, 0.15, 0.25, 0.35, 0.45),
        "effectiveness": (0.35, 0.45, 0.55, 0.70, 0.85),
    }
    results = []
    for parameter, values in tests.items():
        differences = tuple(
            _run_value(simulation_input, definition, config, parameter, value)[0]
            for value in values
        )
        beneficial = [
            value for value, difference in zip(values, differences, strict=True) if difference > 0
        ]
        if parameter == "effectiveness":
            boundary = min(beneficial) if beneficial else None
            interpretation = "minimum tested effectiveness with positive modelled net burden"
        else:
            boundary = max(beneficial) if beneficial else None
            interpretation = f"maximum tested {parameter} with positive modelled net burden"
        results.append(
            ThresholdResult(
                parameter=parameter,
                modelled_boundary=boundary,
                tested_values=values,
                net_burden_differences=differences,
                interpretation=interpretation,
                warnings=("coarse simulation boundary; not a production break-even guarantee",),
            )
        )
    return tuple(results)
