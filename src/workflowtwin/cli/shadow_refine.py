"""CLI entry points for locked refinement and one-time holdout evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from workflowtwin.shadow_refinement.benchmark import (
    compare_dataset,
    comparison_summary,
    pareto_summary,
    sensitivity_summary,
)
from workflowtwin.shadow_refinement.config import StrictV2Config
from workflowtwin.shadow_refinement.protocol import (
    begin_holdout,
    complete_holdout,
    load_refinement_protocol,
)
from workflowtwin.shadow_refinement.reporting import render_markdown, write_json

DEFAULT_PROTOCOL = Path("config/shadow/refinement-protocol.json")


def configure_shadow_refinement_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    refine = subparsers.add_parser("shadow-refine", help="run development and validation A/B")
    holdout = subparsers.add_parser("shadow-holdout", help="run the locked holdout once")
    for parser in (refine, holdout):
        parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
        parser.add_argument("--output-dir", type=Path, default=Path("artifacts/shadow-refinement"))
        parser.add_argument("--force", action="store_true")


def run_shadow_refine(args: argparse.Namespace) -> int:
    protocol = load_refinement_protocol(args.protocol)
    specifications = (*protocol.development_datasets, *protocol.validation_datasets)
    summaries = [
        comparison_summary(*compare_dataset(specification, protocol))
        for specification in specifications
    ]
    config = StrictV2Config()
    payload = {
        "protocol": protocol.model_dump(mode="json"),
        "strict_v2_lock": config.model_dump(mode="json"),
        "strict_v2_fingerprint": config.detector_fingerprint,
        "results": summaries,
        "pareto": pareto_summary(summaries),
        "sensitivity": sensitivity_summary(protocol.validation_datasets[0], protocol),
        "decision": "do_not_promote; retain recommendation-only shadow mode",
    }
    write_json(args.output_dir / "development-validation.json", payload, overwrite=args.force)
    report = render_markdown(summaries, title="Shadow Detector Development and Validation")
    report_path = args.output_dir / "development-validation.md"
    if report_path.exists() and not args.force:
        raise FileExistsError(f"artifact already exists: {report_path}")
    report_path.write_text(report, encoding="utf-8")
    print(f"Evaluated {len(specifications)} pre-registered fictional splits.")
    print(f"Locked strict-v2 fingerprint: {config.detector_fingerprint}")
    print(f"Report: {report_path}")
    return 0


def run_shadow_holdout(args: argparse.Namespace) -> int:
    protocol = load_refinement_protocol(args.protocol)
    config = StrictV2Config()
    registry_path = args.output_dir / "holdout-registry.json"
    output_path = args.output_dir / "holdout.json"
    registry = begin_holdout(
        protocol=protocol,
        detector_fingerprint=config.detector_fingerprint,
        registry_path=registry_path,
    )
    if registry.status == "completed":
        if not output_path.exists():
            raise ValueError("completed holdout registry exists without its immutable result")
        print("Holdout already evaluated once; returning the immutable existing result.")
        print(f"Result: {output_path}")
        return 0
    v1, v2 = compare_dataset(protocol.holdout_dataset, protocol)
    summary = comparison_summary(v1, v2)
    write_json(output_path, summary, overwrite=False)
    complete_holdout(
        registry,
        evaluation_fingerprint=str(summary["comparison_fingerprint"]),
        registry_path=registry_path,
    )
    report_path = args.output_dir / "holdout.md"
    report_path.write_text(
        render_markdown([summary], title="Locked Shadow Holdout"), encoding="utf-8"
    )
    print("Evaluated the untouched 10,000-case fictional holdout exactly once.")
    print(f"Result: {output_path}")
    return 0
