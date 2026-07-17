"""CLI adapter for deterministic recommendation-only shadow replay."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workflowtwin.core.config import get_settings
from workflowtwin.services.baseline_analysis import input_from_database
from workflowtwin.services.shadow_mode import (
    build_shadow_config,
    load_or_generate_snapshots,
    run_shadow,
)
from workflowtwin.shadow.config import DetectorProfile
from workflowtwin.shadow.intake import (
    generate_intake_artifacts,
    load_intake_snapshots,
    write_jsonl,
)
from workflowtwin.shadow.reporting import write_run_artifacts
from workflowtwin.synthetic.artifacts import load_dataset, load_manifest


def configure_shadow_run_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("shadow-run", help="replay fictional intake in shadow mode")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", type=Path)
    source.add_argument("--from-database", action="store_true")
    parser.add_argument("--generation-run")
    parser.add_argument("--database-url")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--intake-snapshots", type=Path)
    parser.add_argument("--opportunity-analysis", type=Path, required=True)
    parser.add_argument("--simulation-analysis", type=Path, required=True)
    parser.add_argument("--run-id", default="northstar-demo-shadow-v1")
    parser.add_argument("--profile", choices=DetectorProfile, default=DetectorProfile.STRICT)
    parser.add_argument("--replay-start")
    parser.add_argument("--replay-end")
    parser.add_argument("--checkpoint-input", type=Path)
    parser.add_argument("--checkpoint-output", type=Path)
    parser.add_argument("--max-source-items", type=int)
    parser.add_argument("--snapshots-output", type=Path)
    parser.add_argument("--labels-output", type=Path)
    parser.add_argument("--recommendations-output", type=Path)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--run-output", type=Path)
    parser.add_argument("--force", action="store_true")


async def _validate_database_source(args: argparse.Namespace) -> None:
    manifest = load_manifest(args.manifest)
    run_id = args.generation_run or manifest.generation_run_id
    engine = create_async_engine(args.database_url or get_settings().database_url)
    sessions = async_sessionmaker[AsyncSession](engine, expire_on_commit=False)
    try:
        source = await input_from_database(sessions, run_id)
    finally:
        await engine.dispose()
    if source.dataset_fingerprint != manifest.dataset_fingerprint:
        raise ValueError("PostgreSQL and manifest dataset fingerprints differ")


def run_shadow_run(args: argparse.Namespace) -> int:
    if args.from_database:
        if args.intake_snapshots is None:
            raise ValueError("--intake-snapshots is required with --from-database")
        asyncio.run(_validate_database_source(args))
        snapshots = load_intake_snapshots(args.intake_snapshots)
    else:
        snapshots = load_or_generate_snapshots(
            dataset_path=args.dataset, snapshots_path=args.intake_snapshots
        )
        if args.intake_snapshots is None and (args.snapshots_output or args.labels_output):
            dataset = load_dataset(args.dataset)
            snapshots, labels = generate_intake_artifacts(dataset)
            if args.snapshots_output:
                write_jsonl(args.snapshots_output, snapshots, overwrite=args.force)
            if args.labels_output:
                write_jsonl(args.labels_output, labels, overwrite=args.force)
    updates: dict[str, object] = {}
    if args.replay_start:
        updates["replay_start"] = args.replay_start
    if args.replay_end:
        updates["replay_end"] = args.replay_end
    config = build_shadow_config(
        run_id=args.run_id,
        profile=DetectorProfile(args.profile),
        manifest_path=args.manifest,
        opportunity_path=args.opportunity_analysis,
        simulation_path=args.simulation_analysis,
        overwrite=args.force,
        **updates,
    )
    run = run_shadow(
        config=config,
        snapshots=snapshots,
        checkpoint_path=args.checkpoint_input,
        max_source_items=args.max_source_items,
    )
    stem = f"{args.run_id}-{config.detector_profile.value}"
    run_output = args.run_output or Path(f"artifacts/shadow/{stem}-run.json")
    recommendations_output = args.recommendations_output or Path(
        f"artifacts/shadow/{stem}-recommendations.jsonl"
    )
    audit_output = args.audit_output or Path(f"artifacts/shadow/{stem}-audit.jsonl")
    write_run_artifacts(
        run,
        run_output=run_output,
        recommendations_output=recommendations_output,
        audit_output=audit_output,
        checkpoint_output=args.checkpoint_output,
        overwrite=args.force,
    )
    print(
        f"Shadow replay {run.manifest.run_status}: {run.manifest.cases_observed} cases, "
        f"{run.manifest.recommendations} recommendations, {run.manifest.abstentions} abstentions."
    )
    print(f"Audit root: {run.manifest.audit_root_fingerprint}")
    print(f"Run: {run_output}")
    return 0
