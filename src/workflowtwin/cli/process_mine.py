"""CLI adapter for deterministic process reconstruction and conformance."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workflowtwin.core.config import get_settings
from workflowtwin.process_mining.analyzer import ProcessMiningAnalyzer
from workflowtwin.process_mining.config import ConformanceMethod, ProcessMiningConfig
from workflowtwin.process_mining.models import ProcessAnalysisInput
from workflowtwin.process_mining.reporting import write_process_artifacts
from workflowtwin.services.process_analysis import (
    load_baseline_analysis,
    process_input_from_database,
    process_input_from_dataset,
)
from workflowtwin.synthetic.artifacts import load_dataset, load_ground_truth, load_manifest


def configure_process_mine_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    process = subparsers.add_parser("process-mine", help="reconstruct fictional referral processes")
    source = process.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", type=Path)
    source.add_argument("--from-database", action="store_true")
    process.add_argument("--generation-run")
    process.add_argument("--database-url")
    process.add_argument("--manifest", type=Path)
    process.add_argument("--baseline-analysis", type=Path)
    process.add_argument("--ground-truth", type=Path)
    process.add_argument("--process-analysis-id", default="northstar-process-v1")
    process.add_argument("--minimum-variant-frequency", type=int, default=2)
    process.add_argument("--rare-variant-threshold", type=int, default=2)
    process.add_argument("--minimum-transition-frequency", type=int, default=5)
    process.add_argument("--minimum-cohort-size", type=int, default=20)
    process.add_argument(
        "--conformance-method",
        choices=ConformanceMethod,
        default=ConformanceMethod.TOKEN_REPLAY,
    )
    process.add_argument("--conformance-timeout", type=float, default=120)
    process.add_argument("--disable-strict-reference", action="store_true")
    process.add_argument("--disable-governed-reference", action="store_true")
    process.add_argument("--analysis-output", type=Path)
    process.add_argument("--report-output", type=Path)
    process.add_argument("--graph-output", type=Path)
    process.add_argument("--case-output", type=Path)
    process.add_argument("--visualisation-directory", type=Path)
    process.add_argument("--force", action="store_true")


async def _database_input(
    database_url: str,
    run_id: str,
    *,
    ground_truth_path: Path | None,
    baseline_path: Path | None,
) -> ProcessAnalysisInput:
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker[AsyncSession](engine, expire_on_commit=False)
    try:
        return await process_input_from_database(
            sessions,
            run_id,
            ground_truth=(load_ground_truth(ground_truth_path) if ground_truth_path else None),
            baseline=(load_baseline_analysis(baseline_path) if baseline_path else None),
        )
    finally:
        await engine.dispose()


def run_process_mine(args: argparse.Namespace) -> int:
    baseline = load_baseline_analysis(args.baseline_analysis) if args.baseline_analysis else None
    ground_truth = load_ground_truth(args.ground_truth) if args.ground_truth else None
    if args.from_database:
        if not args.generation_run:
            raise ValueError("--generation-run is required with --from-database")
        if args.manifest is not None:
            raise ValueError("--manifest is not used with --from-database")
        process_input = asyncio.run(
            _database_input(
                args.database_url or get_settings().database_url,
                args.generation_run,
                ground_truth_path=args.ground_truth,
                baseline_path=args.baseline_analysis,
            )
        )
    else:
        dataset = load_dataset(args.dataset)
        manifest = load_manifest(args.manifest) if args.manifest else None
        process_input = process_input_from_dataset(
            dataset,
            manifest=manifest,
            ground_truth=ground_truth,
            baseline=baseline,
        )
    stem = process_input.operational.generation_run_id or args.process_analysis_id
    analysis_output = args.analysis_output or Path(
        f"artifacts/process/{stem}-process-analysis.json"
    )
    report_output = args.report_output or Path(f"artifacts/process/{stem}-process-report.md")
    graph_output = args.graph_output or Path(f"artifacts/process/{stem}-graph.json")
    config = ProcessMiningConfig(
        analysis_id=args.process_analysis_id,
        source_dataset_fingerprint=process_input.operational.dataset_fingerprint,
        baseline_analysis_fingerprint=(
            baseline.analysis_fingerprint if baseline is not None else None
        ),
        generation_run_id=process_input.operational.generation_run_id,
        minimum_variant_frequency=args.minimum_variant_frequency,
        rare_variant_case_threshold=args.rare_variant_threshold,
        minimum_transition_frequency=args.minimum_transition_frequency,
        minimum_cohort_size=args.minimum_cohort_size,
        conformance_method=args.conformance_method,
        conformance_timeout_seconds=args.conformance_timeout,
        strict_reference_enabled=not args.disable_strict_reference,
        governed_reference_enabled=not args.disable_governed_reference,
        analysis_output=analysis_output,
        report_output=report_output,
        graph_output=graph_output,
        case_output=args.case_output,
        visualisation_directory=args.visualisation_directory,
        overwrite=args.force,
    )
    bundle = ProcessMiningAnalyzer(config).analyze(process_input)
    write_process_artifacts(
        bundle,
        analysis_output=analysis_output,
        report_output=report_output,
        graph_output=graph_output,
        case_output=args.case_output,
        overwrite=args.force,
    )
    analysis = bundle.analysis
    print(f"Process-mined {analysis.case_count} fictional cases and {analysis.event_count} events.")
    print(
        f"Activities: {analysis.complexity.distinct_activity_count}; transitions: "
        f"{analysis.complexity.distinct_transition_count}; variants: "
        f"{analysis.complexity.distinct_variant_count}; top variant: "
        f"{analysis.complexity.top_1_variant_coverage:.1%}."
    )
    strict = analysis.strict_conformance
    governed = analysis.governed_conformance
    print(
        f"Strict conforming: {strict.fully_conforming_rate if strict else None}; "
        f"governed conforming: {governed.fully_conforming_rate if governed else None}; "
        f"candidates: {len(analysis.bottleneck_candidates)}."
    )
    evaluation = analysis.ground_truth_evaluation
    print(
        f"Benchmark detections: {evaluation.detected_count}/{evaluation.planted_count}; "
        f"warnings: {len(analysis.warnings)}."
    )
    print(f"Process fingerprint: {analysis.process_analysis_fingerprint}")
    print(f"JSON: {analysis_output}")
    print(f"Markdown: {report_output}")
    print(f"Graph: {graph_output}")
    return 0
