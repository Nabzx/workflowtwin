"""CLI adapter for supplied or benchmark-only fictional reviewer decisions."""

from __future__ import annotations

import argparse
from pathlib import Path

from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.intake import load_evaluation_labels
from workflowtwin.shadow.reporting import (
    load_recommendations,
    load_run,
    write_reviews,
)
from workflowtwin.shadow.reviews import benchmark_reviews, load_reviews, validate_reviews


def configure_shadow_review_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("shadow-review", help="validate fictional review decisions")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--recommendations", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--reviews", type=Path)
    source.add_argument("--benchmark-labels", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validated-reviews-output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")


def run_shadow_review(args: argparse.Namespace) -> int:
    run = load_run(args.run)
    config = ShadowConfig.model_validate(run.config)
    recommendations = load_recommendations(args.recommendations)
    if recommendations != run.recommendations:
        raise ValueError("recommendation stream does not match the shadow run")
    if args.benchmark_labels:
        reviews = benchmark_reviews(
            recommendations,
            load_evaluation_labels(args.benchmark_labels),
            config,
            seed=args.seed,
        )
    else:
        reviews = validate_reviews(load_reviews(args.reviews), recommendations, config)
    write_reviews(args.validated_reviews_output, reviews, overwrite=args.force)
    print(f"Validated {len(reviews)} fictional review decisions.")
    print(f"Reviews: {args.validated_reviews_output}")
    return 0
