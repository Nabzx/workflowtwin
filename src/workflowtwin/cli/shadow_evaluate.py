"""CLI adapter for hidden-label shadow evaluation and promotion gates."""

from __future__ import annotations

import argparse
from pathlib import Path

from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.intake import load_evaluation_labels, load_intake_snapshots
from workflowtwin.shadow.models import ShadowRun
from workflowtwin.shadow.quality import evaluate_shadow
from workflowtwin.shadow.reporting import (
    load_audit,
    load_recommendations,
    load_run,
    write_evaluation_artifacts,
)
from workflowtwin.shadow.reviews import load_reviews, validate_reviews


def configure_shadow_evaluate_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("shadow-evaluate", help="evaluate a fictional shadow run")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--recommendations", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--intake-snapshots", type=Path, required=True)
    parser.add_argument("--evaluation-labels", type=Path)
    parser.add_argument("--evaluation-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--visualisation-output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")


def run_shadow_evaluate(args: argparse.Namespace) -> int:
    stored_run = load_run(args.run)
    config = ShadowConfig.model_validate(stored_run.config)
    recommendations = load_recommendations(args.recommendations)
    audit = load_audit(args.audit)
    run = ShadowRun.model_validate(
        {
            **stored_run.model_dump(mode="python"),
            "recommendations": recommendations,
            "audit_records": audit,
        }
    )
    reviews = validate_reviews(load_reviews(args.reviews), recommendations, config)
    labels = load_evaluation_labels(args.evaluation_labels) if args.evaluation_labels else ()
    evaluation = evaluate_shadow(
        run=run,
        snapshots=load_intake_snapshots(args.intake_snapshots),
        labels=labels,
        reviews=reviews,
        config=config,
    )
    write_evaluation_artifacts(
        evaluation,
        evaluation_output=args.evaluation_output,
        report_output=args.report_output,
        visualisation_output=args.visualisation_output,
        overwrite=args.force,
    )
    print(
        f"Shadow evaluation: precision={evaluation.detector.precision.value}; "
        f"recall={evaluation.detector.recall.value}; "
        f"assessment={evaluation.promotion_assessment.result}."
    )
    print(f"Fingerprint: {evaluation.evaluation_fingerprint}")
    return 0
