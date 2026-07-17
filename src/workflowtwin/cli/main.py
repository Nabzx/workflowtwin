"""Non-interactive CLI for generation, validation, and baseline analysis."""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workflowtwin.analytics.reporting import AnalysisArtifactExistsError
from workflowtwin.cli.analyze import configure_analyze_parser, run_analyze
from workflowtwin.cli.identify_opportunities import (
    configure_identify_opportunities_parser,
    run_identify_opportunities,
)
from workflowtwin.cli.process_mine import configure_process_mine_parser, run_process_mine
from workflowtwin.core.config import get_settings
from workflowtwin.opportunities.reporting import OpportunityArtifactExistsError
from workflowtwin.process_mining.adapters.pm4py import Pm4pyAdapterError
from workflowtwin.process_mining.reporting import ProcessArtifactExistsError
from workflowtwin.services.baseline_analysis import AnalysisInputError
from workflowtwin.services.synthetic_generation import (
    GenerationPersistenceError,
    SyntheticGenerationService,
)
from workflowtwin.synthetic.artifacts import (
    ArtifactExistsError,
    load_dataset,
    write_dataset,
    write_ground_truth,
    write_manifest,
    write_validation_report,
)
from workflowtwin.synthetic.config import OutputMode
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.models import GeneratedDataset
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset
from workflowtwin.synthetic.validation import validate_dataset


async def _persist_dataset(database_url: str, dataset: GeneratedDataset, batch_size: int) -> str:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker[AsyncSession](engine, expire_on_commit=False)
    try:
        result = await SyntheticGenerationService(session_factory, batch_size=batch_size).persist(
            dataset
        )
        return result.status.value
    finally:
        await engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workflowtwin")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="generate fictional referral event data")
    generate.add_argument("--preset", choices=GenerationPreset, default=GenerationPreset.TINY)
    generate.add_argument("--seed", type=int)
    generate.add_argument("--cases", type=int)
    generate.add_argument("--start-date", type=str)
    generate.add_argument("--days", type=int)
    generate.add_argument("--timezone", type=str)
    generate.add_argument("--run-id", type=str)
    generate.add_argument("--batch-size", type=int)
    generate.add_argument("--persist", action="store_true")
    generate.add_argument("--database-url", type=str)
    generate.add_argument("--manifest-output", type=Path)
    generate.add_argument("--ground-truth-output", type=Path)
    generate.add_argument("--dataset-output", type=Path)
    generate.add_argument("--validation-output", type=Path)
    generate.add_argument("--force", action="store_true")

    validate = subparsers.add_parser("validate", help="validate an exported synthetic dataset")
    validate.add_argument("--dataset", type=Path, required=True)
    validate.add_argument("--report-output", type=Path)
    validate.add_argument("--force", action="store_true")
    configure_analyze_parser(subparsers)
    configure_process_mine_parser(subparsers)
    configure_identify_opportunities_parser(subparsers)
    return parser


def _generate(args: argparse.Namespace) -> int:
    overrides: dict[str, object] = {"output_mode": OutputMode.ARTIFACTS}
    if args.seed is not None:
        overrides["seed"] = args.seed
    if args.cases is not None:
        overrides["case_count"] = args.cases
    if args.days is not None:
        overrides["operating_days"] = args.days
    if args.timezone is not None:
        overrides["source_timezone"] = args.timezone
    if args.run_id is not None:
        overrides["generation_run_id"] = args.run_id
    if args.batch_size is not None:
        overrides["batch_size"] = args.batch_size
    if args.persist:
        overrides["persist"] = True
    if args.start_date is not None:
        source_timezone = str(overrides.get("source_timezone", "Europe/London"))
        overrides["period_start"] = datetime.combine(
            datetime.fromisoformat(args.start_date).date(),
            time(),
            tzinfo=ZoneInfo(source_timezone),
        )

    config = config_for_preset(GenerationPreset(args.preset), **overrides)
    dataset = SyntheticReferralGenerator(config).generate()
    report = validate_dataset(dataset)
    if not report.is_valid:
        print("Generated dataset failed validation.", file=sys.stderr)
        return 2

    run_id = dataset.manifest.generation_run_id
    manifest_path = args.manifest_output or Path(f"artifacts/generation/{run_id}-manifest.json")
    ground_truth_path = args.ground_truth_output or Path(
        f"artifacts/generation/{run_id}-ground-truth.json"
    )
    write_manifest(manifest_path, dataset.manifest, overwrite=args.force)
    write_ground_truth(ground_truth_path, dataset.ground_truth, overwrite=args.force)
    if args.dataset_output is not None:
        write_dataset(args.dataset_output, dataset, overwrite=args.force)
    if args.validation_output is not None:
        write_validation_report(args.validation_output, report, overwrite=args.force)

    persistence_status = "not requested"
    if args.persist:
        settings = get_settings()
        database_url = args.database_url or settings.database_url
        persistence_status = asyncio.run(_persist_dataset(database_url, dataset, config.batch_size))

    print(
        f"Generated {len(dataset.cases)} fictional cases and {len(dataset.events)} events "
        f"for run {run_id}."
    )
    print(f"Fingerprint: {dataset.manifest.dataset_fingerprint}")
    print(f"Validation: valid; persistence: {persistence_status}")
    print(f"Manifest: {manifest_path}")
    print(f"Ground truth: {ground_truth_path}")
    return 0


def _validate(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    report = validate_dataset(dataset)
    if args.report_output is not None:
        write_validation_report(args.report_output, report, overwrite=args.force)
    print(
        f"Validated {report.case_count} cases and {report.event_count} events: "
        f"{'valid' if report.is_valid else 'invalid'}."
    )
    for finding in report.findings:
        print(f"{finding.severity.value}: {finding.code} ({finding.count})")
    return 0 if report.is_valid else 2


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a CLI command and translate expected failures to a non-zero code."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "generate":
            return _generate(args)
        if args.command == "analyze":
            return run_analyze(args)
        if args.command == "process-mine":
            return run_process_mine(args)
        if args.command == "identify-opportunities":
            return run_identify_opportunities(args)
        return _validate(args)
    except (
        AnalysisArtifactExistsError,
        AnalysisInputError,
        Pm4pyAdapterError,
        ProcessArtifactExistsError,
        OpportunityArtifactExistsError,
        ArtifactExistsError,
        GenerationPersistenceError,
        OSError,
        ValidationError,
        ValueError,
    ) as error:
        print(f"workflowtwin: {error}", file=sys.stderr)
        return 1


def entrypoint() -> None:
    raise SystemExit(main())
