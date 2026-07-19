"""CLI for the single supported recommendation-only detector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflowtwin.detector import CompletenessReviewDetector
from workflowtwin.intake.requirements import load_northstar_requirements
from workflowtwin.source_contracts.generator import generate_v2_intake_artifacts
from workflowtwin.synthetic.artifacts import load_dataset


def configure_shadow_run_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "shadow-run", help="run the supported completeness detector on fictional data"
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--run-id", default="northstar-supported-shadow-run")
    parser.add_argument("--output", type=Path, default=Path("artifacts/shadow/supported-run.json"))
    parser.add_argument("--force", action="store_true")


def run_shadow_run(args: argparse.Namespace) -> int:
    if args.output.exists() and not args.force:
        raise FileExistsError("supported shadow artifact already exists; use --force")
    dataset = load_dataset(args.dataset)
    requirements = load_northstar_requirements()
    snapshots, _ = generate_v2_intake_artifacts(dataset, requirements)
    detector = CompletenessReviewDetector(requirements)
    run = detector.run(snapshots, run_id=args.run_id)
    payload = {
        "fictional": True,
        "intake_contract": "Northstar intake contract",
        "detector": detector.lineage.model_dump(mode="json"),
        "run": run.model_dump(mode="json"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Supported shadow run: {len(dataset.cases)} fictional cases, "
        f"{len(run.detector_positive_case_ids)} detector positives."
    )
    print(f"Detector: {detector.lineage.product_name} (derived from strict-v3)")
    print(f"Output: {args.output}")
    return 0
