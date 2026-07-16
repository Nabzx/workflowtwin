"""CLI adapter for deterministic baseline analysis."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.models import AnalysisInput
from workflowtwin.analytics.reporting import write_analysis_artifacts
from workflowtwin.core.config import get_settings
from workflowtwin.services.baseline_analysis import input_from_database, input_from_dataset
from workflowtwin.synthetic.artifacts import load_dataset, load_ground_truth, load_manifest


def configure_analyze_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    analyze = subparsers.add_parser("analyze", help="analyse fictional referral operations")
    source = analyze.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", type=Path)
    source.add_argument("--from-database", action="store_true")
    analyze.add_argument("--generation-run", type=str)
    analyze.add_argument("--database-url", type=str)
    analyze.add_argument("--manifest", type=Path)
    analyze.add_argument("--ground-truth", type=Path)
    analyze.add_argument("--analysis-id", default="northstar-baseline-v1")
    analyze.add_argument("--stuck-threshold", type=float, default=120)
    analyze.add_argument("--minimum-cohort-size", type=int, default=20)
    analyze.add_argument("--report-output", type=Path)
    analyze.add_argument("--analysis-output", type=Path)
    analyze.add_argument("--case-metrics-output", type=Path)
    analyze.add_argument("--force", action="store_true")


async def _database_input(database_url: str, run_id: str) -> AnalysisInput:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker[AsyncSession](engine, expire_on_commit=False)
    try:
        return await input_from_database(session_factory, run_id)
    finally:
        await engine.dispose()


def run_analyze(args: argparse.Namespace) -> int:
    """Load one source, run the analyzer, and emit safe report artifacts."""
    if args.from_database:
        if not args.generation_run:
            raise ValueError("--generation-run is required with --from-database")
        if args.manifest is not None:
            raise ValueError("--manifest is not used with --from-database")
        database_url = args.database_url or get_settings().database_url
        analysis_input = asyncio.run(_database_input(database_url, args.generation_run))
    else:
        dataset = load_dataset(args.dataset)
        supplied_manifest = load_manifest(args.manifest) if args.manifest else None
        analysis_input = input_from_dataset(dataset, manifest=supplied_manifest)
    if args.ground_truth is not None:
        analysis_input = replace(analysis_input, ground_truth=load_ground_truth(args.ground_truth))
    stem = analysis_input.generation_run_id or args.analysis_id
    analysis_output = args.analysis_output or Path(f"artifacts/analysis/{stem}-analysis.json")
    report_output = args.report_output or Path(f"artifacts/analysis/{stem}-report.md")
    config = AnalysisConfig(
        analysis_id=args.analysis_id,
        stuck_threshold_hours=args.stuck_threshold,
        minimum_cohort_size=args.minimum_cohort_size,
        analysis_output=analysis_output,
        report_output=report_output,
        case_metrics_output=args.case_metrics_output,
        source_dataset_fingerprint=analysis_input.dataset_fingerprint,
        generation_run_id=analysis_input.generation_run_id,
    )
    bundle = BaselineAnalyzer(config).analyze(analysis_input)
    write_analysis_artifacts(
        bundle,
        analysis_output=analysis_output,
        report_output=report_output,
        case_metrics_output=args.case_metrics_output,
        overwrite=args.force,
    )
    baseline = bundle.baseline
    completion = baseline.overall.rates["completion_rate"].value
    median_duration = baseline.overall.summaries["case_duration_hours"].median
    evaluation = baseline.ground_truth_evaluation
    completion_text = "unavailable" if completion is None else f"{completion:.1%}"
    duration_text = "unavailable" if median_duration is None else f"{median_duration:.2f}h"
    print(f"Analysed {baseline.case_count} fictional cases and {baseline.event_count} events.")
    print(
        f"Completion: {completion_text}; median duration: {duration_text}; "
        f"findings: {len(baseline.findings)}."
    )
    print(
        f"Coverage warnings: {len(baseline.warnings)}; benchmark detections: "
        f"{evaluation.detected_count}/{evaluation.planted_count}."
    )
    print(f"Analysis fingerprint: {baseline.analysis_fingerprint}")
    print(f"JSON: {analysis_output}")
    print(f"Markdown: {report_output}")
    return 0
