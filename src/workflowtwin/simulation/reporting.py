"""Safe JSON, JSONL, and stakeholder Markdown simulation artifacts."""

import json
from pathlib import Path
from typing import Any

from workflowtwin.simulation.models import SimulationAnalysis


class SimulationArtifactExistsError(FileExistsError):
    """Raised when a simulation output would overwrite an existing artifact."""


def _preflight(paths: tuple[Path | None, ...], *, overwrite: bool) -> None:
    if overwrite:
        return
    for path in paths:
        if path is not None and path.exists():
            raise SimulationArtifactExistsError(f"simulation artifact already exists: {path}")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def render_report(analysis: SimulationAnalysis) -> str:
    scenario = analysis.scenario_result
    manifest = scenario.manifest
    burden = scenario.burden_comparison
    selected = analysis.selected_opportunity
    metric_rows = "\n".join(
        "| {name} | {baseline} | {simulated} | {difference} | {classification} |".format(
            name=item.metric_name,
            baseline="unavailable" if item.baseline_value is None else f"{item.baseline_value:.4g}",
            simulated="unavailable"
            if item.simulated_value is None
            else f"{item.simulated_value:.4g}",
            difference="unavailable"
            if item.absolute_difference is None
            else f"{item.absolute_difference:+.4g}",
            classification=item.effect_classification.value,
        )
        for item in scenario.metric_comparisons
    )
    thresholds = (
        "\n".join(
            f"- `{item.parameter}`: {item.interpretation} = "
            f"{item.modelled_boundary if item.modelled_boundary is not None else 'not found'}"
            for item in analysis.threshold_results
        )
        or "- Not run."
    )
    controls = "\n".join(f"- {item}" for item in analysis.decision.required_additional_controls)
    shadow = "\n".join(
        f"- **{item.category}:** {item.requirement}" for item in analysis.shadow_mode_requirements
    )
    case_counts = (
        f"{manifest.source_case_count} / {manifest.eligible_case_count} / "
        f"{manifest.affected_case_count}"
    )
    control_counts = (
        f"{manifest.review_required_count} / {manifest.fallback_count} / "
        f"{manifest.intervention_failure_count} / {manifest.rollback_count}"
    )
    return f"""# Fictional counterfactual intervention simulation

> {analysis.fictional_counterfactual_declaration}

## Executive summary

WorkflowTwin selected `{selected.opportunity_id}`, the sole controlled-prototype opportunity, and
modelled `{analysis.intervention_definition.intervention_id}` under the `{scenario.scenario_id}`
scenario. The result is `{analysis.decision.status.value}`. This supports decision-making about a
possible later shadow-mode experiment only; it is not deployment approval or realised impact.

## Evidence chain

Observed baseline problem
→ evidence-backed GP-practice completeness opportunity
→ guarded recommendation-only intervention
→ human approval and counterfactual event overlay
→ existing baseline and process engines
→ scenario, failure, sensitivity and threshold analysis
→ shadow-mode decision

## Intervention boundary

Allowed: observe structured administrative fields, recommend a completeness review, request named
human approval, record an approved simulated validation, fall back, and roll back.

Prohibited: {"; ".join(analysis.intervention_definition.prohibited_actions)}.

## Scenario assumptions

- Rollout: {manifest.configured_rates["rollout_percentage"]:.1%}
- Effectiveness: {manifest.configured_rates["effectiveness"]:.1%}
- False-positive assumption: {manifest.configured_rates["false_positive_rate"]:.1%}
- False-negative assumption: {manifest.configured_rates["false_negative_rate"]:.1%}
- Source / eligible / affected cases: {case_counts}
- Reviews / fallbacks / failures / rollbacks: {control_counts}

## Metric comparison

| Metric | Baseline | Simulated | Difference | Classification |
| --- | ---: | ---: | ---: | --- |
{metric_rows}

## Burden and cost proxy

- Baseline associated manual-touch burden: {burden.baseline_manual_touch_hours:.3f} hours.
- Simulated workflow-touch burden: {burden.simulated_workflow_touch_hours:.3f} hours.
- Review, fallback and recovery overhead: {burden.simulated_operating_burden_hours:.3f} hours.
- Net simulated burden difference: {burden.net_simulated_difference_hours:+.3f} hours.
- Net fictional cost-proxy difference: GBP {burden.simulated_net_cost_difference_gbp:+.2f}.
- Addressable upper bound: {burden.addressable_upper_bound_hours:.3f} hours; not a forecast.

## Direct, secondary, control and adverse effects

Direct: {"; ".join(scenario.direct_effects) or "none measured"}.

Secondary: {"; ".join(scenario.secondary_effects) or "none measured"}.

Control overhead: {"; ".join(scenario.control_overhead)}.

Adverse: {"; ".join(scenario.adverse_effects)}.

## Process comparison

The modelled process has {scenario.counterfactual_process_summary.variant_count} variants versus
{scenario.baseline_process_summary.variant_count} at baseline. Governed fully conforming rates are
{scenario.baseline_process_summary.governed_fully_conforming_rate} baseline and
{scenario.counterfactual_process_summary.governed_fully_conforming_rate} simulated. Intervention
control records remain outside the operational activity vocabulary.

## Sensitivity and break-even boundaries

Sensitivity ran {len(analysis.sensitivity_results)} one-at-a-time tests. These are coarse,
assumption-dependent boundaries, not production guarantees.

{thresholds}

## Decision controls

{controls}

## Future shadow-mode requirements

{shadow}

## Benchmark and limitations

Post-simulation benchmark: {analysis.benchmark_evaluation.passed_count}/
{analysis.benchmark_evaluation.check_count}. Source events remained unchanged:
{str(scenario.quality.source_events_unchanged).lower()}.

All data and research are fictional. Effects are modelled from explicit rules and assumptions, not
causal estimates. No automation ran, no external communication occurred, no production saving was
achieved, and no clinical conclusion can be drawn.

Simulation fingerprint: `{analysis.simulation_analysis_fingerprint}`
"""


def write_simulation_artifacts(
    analysis: SimulationAnalysis,
    *,
    analysis_output: Path,
    report_output: Path,
    comparison_output: Path,
    case_output: Path | None,
    overwrite: bool,
) -> None:
    _preflight(
        (analysis_output, report_output, comparison_output, case_output),
        overwrite=overwrite,
    )
    _write(analysis_output, _json(analysis))
    _write(report_output, render_report(analysis))
    _write(comparison_output, _json(analysis.graph_data))
    if case_output is not None:
        lines = "".join(
            json.dumps(item.model_dump(mode="json"), sort_keys=True) + "\n"
            for item in analysis.scenario_result.case_results
        )
        _write(case_output, lines)
