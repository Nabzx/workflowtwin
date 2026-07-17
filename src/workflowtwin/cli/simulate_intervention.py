"""CLI adapter for controlled counterfactual intervention simulation."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workflowtwin.core.config import get_settings
from workflowtwin.services.intervention_simulation import (
    load_database_simulation_input,
    load_file_simulation_input,
)
from workflowtwin.simulation.analyzer import InterventionSimulator
from workflowtwin.simulation.config import (
    SCENARIOS,
    ScenarioId,
    ScenarioParameters,
    config_for_scenario,
)
from workflowtwin.simulation.models import SimulationInput
from workflowtwin.simulation.reporting import write_simulation_artifacts
from workflowtwin.simulation.selection import select_controlled_prototype


def configure_simulate_intervention_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "simulate-intervention",
        help="simulate one guarded fictional administrative intervention",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", type=Path)
    source.add_argument("--from-database", action="store_true")
    parser.add_argument("--generation-run")
    parser.add_argument("--database-url")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--baseline-analysis", type=Path, required=True)
    parser.add_argument("--process-analysis", type=Path, required=True)
    parser.add_argument("--opportunity-analysis", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--scenario", choices=ScenarioId, default=ScenarioId.CENTRAL)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rollout", type=float)
    parser.add_argument("--effectiveness", type=float)
    parser.add_argument("--false-positive-rate", type=float)
    parser.add_argument("--false-negative-rate", type=float)
    parser.add_argument("--reviewer-turnaround-max-hours", type=float)
    parser.add_argument("--fallback-rate", type=float)
    parser.add_argument("--analysis-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--comparison-output", type=Path)
    parser.add_argument("--case-output", type=Path)
    parser.add_argument("--skip-sensitivity", action="store_true")
    parser.add_argument("--force", action="store_true")


async def _load_database(args: argparse.Namespace) -> SimulationInput:
    if not args.generation_run:
        raise ValueError("--generation-run is required with --from-database")
    database_url = args.database_url or get_settings().database_url
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker[AsyncSession](engine, expire_on_commit=False)
    try:
        return await load_database_simulation_input(
            session_factory=sessions,
            generation_run_id=args.generation_run,
            baseline_path=args.baseline_analysis,
            process_path=args.process_analysis,
            opportunity_path=args.opportunity_analysis,
            ground_truth_path=args.ground_truth,
        )
    finally:
        await engine.dispose()


def _parameters(args: argparse.Namespace, scenario: ScenarioId) -> ScenarioParameters:
    parameters = SCENARIOS[scenario]
    updates: dict[str, object] = {}
    for argument, field in (
        (args.rollout, "rollout_percentage"),
        (args.effectiveness, "effectiveness"),
        (args.false_positive_rate, "false_positive_rate"),
        (args.false_negative_rate, "false_negative_rate"),
        (args.fallback_rate, "manual_fallback_rate"),
    ):
        if argument is not None:
            updates[field] = argument
    if args.reviewer_turnaround_max_hours is not None:
        updates["human_review_turnaround_hours"] = (
            parameters.human_review_turnaround_hours[0],
            args.reviewer_turnaround_max_hours,
        )
    return parameters.model_copy(update=updates)


def run_simulate_intervention(args: argparse.Namespace) -> int:
    if args.from_database:
        simulation_input = asyncio.run(_load_database(args))
    else:
        if args.manifest is None:
            raise ValueError("--manifest is required with --dataset")
        simulation_input = load_file_simulation_input(
            dataset_path=args.dataset,
            manifest_path=args.manifest,
            baseline_path=args.baseline_analysis,
            process_path=args.process_analysis,
            opportunity_path=args.opportunity_analysis,
            ground_truth_path=args.ground_truth,
        )
    candidate = select_controlled_prototype(simulation_input.opportunities)
    scenario = ScenarioId(args.scenario)
    stem = f"{scenario.value}-simulation"
    analysis_output = args.analysis_output or Path(f"artifacts/simulation/{stem}.json")
    report_output = args.report_output or Path(f"artifacts/simulation/{stem}.md")
    comparison_output = args.comparison_output or Path(
        f"artifacts/simulation/{stem}-comparison.json"
    )
    config = config_for_scenario(
        scenario_id=scenario,
        selected_opportunity_id=candidate.opportunity_id,
        source_dataset_fingerprint=simulation_input.source.dataset_fingerprint,
        baseline_analysis_fingerprint=simulation_input.baseline.analysis_fingerprint,
        process_analysis_fingerprint=(simulation_input.process.process_analysis_fingerprint),
        opportunity_analysis_fingerprint=(
            simulation_input.opportunities.opportunity_analysis_fingerprint
        ),
        generation_run_id=simulation_input.source.generation_run_id,
        simulation_seed=args.seed,
        parameters=_parameters(args, scenario),
        analysis_output=analysis_output,
        report_output=report_output,
        comparison_output=comparison_output,
        case_output=args.case_output,
        overwrite=args.force,
    )
    analysis = InterventionSimulator(config).analyze(
        simulation_input,
        include_sensitivity=not args.skip_sensitivity,
    )
    write_simulation_artifacts(
        analysis,
        analysis_output=analysis_output,
        report_output=report_output,
        comparison_output=comparison_output,
        case_output=args.case_output,
        overwrite=args.force,
    )
    result = analysis.scenario_result
    manifest = result.manifest
    burden = result.burden_comparison
    print(f"Selected opportunity: {candidate.opportunity_id}")
    print(f"Intervention: {analysis.intervention_definition.intervention_id}")
    print(
        f"Cases: {manifest.source_case_count} source; {manifest.eligible_case_count} eligible; "
        f"{manifest.affected_case_count} affected; {manifest.review_required_count} reviewed."
    )
    print(
        f"Fallbacks: {manifest.fallback_count}; failures: "
        f"{manifest.intervention_failure_count}; adverse paths: "
        f"{manifest.rejected_action_count + manifest.rollback_count}."
    )
    print(
        f"Simulated net burden difference: {burden.net_simulated_difference_hours:+.3f} "
        f"hours; control overhead: {burden.simulated_operating_burden_hours:.3f} hours."
    )
    print(
        f"Scenario: {scenario.value}; decision: {analysis.decision.status.value}; "
        f"warnings: {len(analysis.warnings) + len(result.quality.warnings)}."
    )
    print(f"Simulation fingerprint: {analysis.simulation_analysis_fingerprint}")
    print(f"JSON: {analysis_output}")
    print(f"Markdown: {report_output}")
    print(f"Comparison: {comparison_output}")
    return 0
