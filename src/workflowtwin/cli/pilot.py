"""CLI commands for deterministic pilot evidence and the local demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflowtwin.pilot.demo import build_demo_pilot
from workflowtwin.pilot.pipeline import run_supported_analysis_pipeline
from workflowtwin.pilot.reporting import write_pilot_artifacts


def configure_pilot_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    pilot = subparsers.add_parser("pilot-run", help="evaluate the fictional controlled pilot")
    pilot.add_argument("--output-dir", type=Path, default=Path("artifacts/pilot"))
    pilot.add_argument("--reset", action="store_true")

    demo = subparsers.add_parser("demo", help="prepare the supported local product demo")
    demo.add_argument("--output-dir", type=Path, default=Path("artifacts/demo"))
    demo.add_argument("--reset", action="store_true")
    demo.add_argument("--skip-heavy-analysis", action="store_true")


def run_pilot(args: argparse.Namespace) -> int:
    run, _ = build_demo_pilot()
    json_path, report_path = write_pilot_artifacts(run, args.output_dir, overwrite=args.reset)
    print(f"Pilot assessment: {run.assessment.value}")
    print(
        f"Surfaced workload: {run.metrics.surfaced_recommendation_coverage:.1%}; "
        f"detector positives: {run.metrics.detector_positive_coverage:.1%}."
    )
    print("No message was sent and no operational referral event was changed.")
    print(f"Pilot JSON: {json_path}")
    print(f"Pilot report: {report_path}")
    return 0


def run_demo(args: argparse.Namespace) -> int:
    result = run_pilot(args)
    manifest_path = args.output_dir / "demo-seed.json"
    run, _ = build_demo_pilot()
    manifest = {
        "demo_version": "northstar-supported-demo-v1",
        "fictional": True,
        "skip_heavy_analysis": args.skip_heavy_analysis,
        "supported_intake": "Northstar intake contract",
        "supported_detector": run.supported_detector_metadata,
        "pilot_run": "pilot-run.json",
        "pilot_report": "pilot-report.md",
        "api_command": "uv run workflowtwin serve",
        "no_message_sent": True,
        "pipeline": (
            {"heavy_analysis_completed": False}
            if args.skip_heavy_analysis
            else run_supported_analysis_pipeline()
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("Local API: uv run workflowtwin serve")
    print(f"Demo seed: {manifest_path}")
    return result
