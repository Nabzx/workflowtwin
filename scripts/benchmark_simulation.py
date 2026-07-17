"""Benchmark the fixed 10,000-case counterfactual pipeline without runtime assertions."""

import argparse
import json
import tracemalloc
from pathlib import Path
from time import perf_counter

from workflowtwin.services.intervention_simulation import load_file_simulation_input
from workflowtwin.simulation.analysis import (
    analyze_counterfactual_baseline,
    analyze_counterfactual_process,
)
from workflowtwin.simulation.comparisons import compare_burden, compare_metrics
from workflowtwin.simulation.config import ScenarioId, config_for_scenario
from workflowtwin.simulation.counterfactuals import CounterfactualSimulator
from workflowtwin.simulation.fingerprint import stable_hash
from workflowtwin.simulation.interventions import define_intervention
from workflowtwin.simulation.selection import validate_selected_opportunity

SELECTED_OPPORTUNITY_ID = "opportunity-7def8c82e8b589e5"


def benchmark(
    *,
    dataset_path: Path,
    manifest_path: Path,
    baseline_path: Path,
    process_path: Path,
    opportunity_path: Path,
    ground_truth_path: Path | None,
) -> dict[str, int | float | str | None]:
    simulation_input = load_file_simulation_input(
        dataset_path=dataset_path,
        manifest_path=manifest_path,
        baseline_path=baseline_path,
        process_path=process_path,
        opportunity_path=opportunity_path,
        ground_truth_path=ground_truth_path,
    )
    candidate = validate_selected_opportunity(
        simulation_input.opportunities, SELECTED_OPPORTUNITY_ID
    )
    definition = define_intervention(candidate)
    config = config_for_scenario(
        scenario_id=ScenarioId.CENTRAL,
        selected_opportunity_id=candidate.opportunity_id,
        source_dataset_fingerprint=simulation_input.source.dataset_fingerprint,
        baseline_analysis_fingerprint=simulation_input.baseline.analysis_fingerprint,
        process_analysis_fingerprint=(simulation_input.process.process_analysis_fingerprint),
        opportunity_analysis_fingerprint=(
            simulation_input.opportunities.opportunity_analysis_fingerprint
        ),
        generation_run_id=simulation_input.source.generation_run_id,
    )

    tracemalloc.start()
    started = perf_counter()
    counterfactual = CounterfactualSimulator(config).simulate(simulation_input, definition)
    counterfactual_seconds = perf_counter() - started
    baseline_started = perf_counter()
    baseline = analyze_counterfactual_baseline(simulation_input, counterfactual)
    baseline_seconds = perf_counter() - baseline_started
    process_started = perf_counter()
    process = analyze_counterfactual_process(simulation_input, counterfactual, baseline)
    process_seconds = perf_counter() - process_started
    comparisons = compare_metrics(simulation_input.baseline, baseline.baseline, candidate)
    burden = compare_burden(
        simulation_input.baseline,
        baseline.baseline,
        candidate,
        counterfactual.case_results,
        config,
    )
    total_seconds = perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    manual = next(item for item in comparisons if item.metric_name == "manual_touches")
    first_check = next(
        item for item in comparisons if item.metric_name == "time_to_first_completeness_check_hours"
    )
    serialized_manifest = counterfactual.manifest.model_dump_json().encode()
    serialized_cases = "\n".join(
        item.model_dump_json() for item in counterfactual.case_results
    ).encode()
    benchmark_fingerprint = stable_hash(
        {
            "manifest": counterfactual.manifest,
            "baseline": baseline.baseline.analysis_fingerprint,
            "process": process.analysis.process_analysis_fingerprint,
            "comparisons": comparisons,
            "burden": burden,
        }
    )
    return {
        "source_cases": len(simulation_input.source.cases),
        "source_events": len(simulation_input.source.events),
        "eligible_cases": counterfactual.manifest.eligible_case_count,
        "affected_cases": counterfactual.manifest.affected_case_count,
        "counterfactual_events": len(counterfactual.operational.events),
        "counterfactual_seconds": round(counterfactual_seconds, 3),
        "baseline_analysis_seconds": round(baseline_seconds, 3),
        "process_analysis_seconds": round(process_seconds, 3),
        "total_seconds": round(total_seconds, 3),
        "traced_peak_memory_mib": round(peak_bytes / 1024 / 1024, 1),
        "manifest_json_bytes": len(serialized_manifest),
        "case_jsonl_bytes": len(serialized_cases),
        "manual_touches_difference_per_case": manual.absolute_difference,
        "first_check_hours_difference": first_check.absolute_difference,
        "control_overhead_hours": burden.simulated_operating_burden_hours,
        "net_burden_difference_hours": burden.net_simulated_difference_hours,
        "fallback_count": counterfactual.manifest.fallback_count,
        "failure_count": counterfactual.manifest.intervention_failure_count,
        "decision": (
            "proceed_only_with_additional_controls"
            if burden.net_simulated_difference_hours > 0
            else "revise_intervention_design"
        ),
        "benchmark_fingerprint": benchmark_fingerprint,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("artifacts/generation/full-dataset.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/generation/northstar-full-42-manifest.json"),
    )
    parser.add_argument(
        "--baseline-analysis",
        type=Path,
        default=Path("artifacts/analysis/full-analysis.json"),
    )
    parser.add_argument(
        "--process-analysis",
        type=Path,
        default=Path("artifacts/process/full-process-analysis.json"),
    )
    parser.add_argument(
        "--opportunity-analysis",
        type=Path,
        default=Path("artifacts/opportunities/full-opportunities.json"),
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("artifacts/generation/northstar-full-42-ground-truth.json"),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            benchmark(
                dataset_path=args.dataset,
                manifest_path=args.manifest,
                baseline_path=args.baseline_analysis,
                process_path=args.process_analysis,
                opportunity_path=args.opportunity_analysis,
                ground_truth_path=args.ground_truth,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
