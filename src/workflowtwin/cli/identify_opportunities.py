"""CLI adapter for evidence-backed opportunity identification."""

from __future__ import annotations

import argparse
from pathlib import Path

from workflowtwin.opportunities.analyzer import OpportunityIdentifier
from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.reporting import write_opportunity_artifacts
from workflowtwin.services.opportunity_analysis import load_opportunity_input


def configure_identify_opportunities_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "identify-opportunities",
        help="rank evidence-backed fictional administrative opportunities",
    )
    parser.add_argument("--baseline-analysis", type=Path, required=True)
    parser.add_argument("--process-analysis", type=Path, required=True)
    parser.add_argument("--research-pack", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--opportunity-analysis-id", default="northstar-opportunities-v1")
    parser.add_argument("--minimum-sample-size", type=int, default=20)
    parser.add_argument("--administrative-cost-per-hour", type=float, default=24.0)
    parser.add_argument("--manual-touch-minutes", type=float, default=5.0)
    parser.add_argument("--value-weight", type=float, default=0.40)
    parser.add_argument("--readiness-weight", type=float, default=0.25)
    parser.add_argument("--confidence-weight", type=float, default=0.25)
    parser.add_argument("--risk-weight", type=float, default=0.10)
    parser.add_argument("--analysis-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--portfolio-output", type=Path)
    parser.add_argument("--evidence-output", type=Path)
    parser.add_argument("--force", action="store_true")


def run_identify_opportunities(args: argparse.Namespace) -> int:
    stem = args.opportunity_analysis_id
    analysis_output = args.analysis_output or Path(f"artifacts/opportunities/{stem}-analysis.json")
    report_output = args.report_output or Path(f"artifacts/opportunities/{stem}-report.md")
    portfolio_output = args.portfolio_output or Path(
        f"artifacts/opportunities/{stem}-portfolio.json"
    )
    evidence_output = args.evidence_output or Path(
        f"artifacts/opportunities/{stem}-evidence-network.json"
    )
    config = OpportunityConfig(
        analysis_id=args.opportunity_analysis_id,
        minimum_sample_size=args.minimum_sample_size,
        administrative_cost_per_hour_gbp=args.administrative_cost_per_hour,
        manual_touch_minutes_proxy=args.manual_touch_minutes,
        value_weight=args.value_weight,
        readiness_weight=args.readiness_weight,
        confidence_weight=args.confidence_weight,
        risk_weight=args.risk_weight,
        analysis_output=analysis_output,
        report_output=report_output,
        portfolio_output=portfolio_output,
        evidence_output=evidence_output,
        overwrite=args.force,
    )
    analysis_input = load_opportunity_input(
        baseline_path=args.baseline_analysis,
        process_path=args.process_analysis,
        research_path=args.research_pack,
        manifest_path=args.manifest,
        ground_truth_path=args.ground_truth,
        config=config,
    )
    analysis = OpportunityIdentifier(config).analyze(analysis_input)
    write_opportunity_artifacts(
        analysis,
        analysis_output=analysis_output,
        report_output=report_output,
        portfolio_output=portfolio_output,
        evidence_output=evidence_output,
        overwrite=args.force,
    )
    portfolio = analysis.portfolio
    top = analysis.candidates[0].opportunity_id if analysis.candidates else "none"
    print(
        f"Loaded {analysis.evidence_quality.total_evidence_count} evidence records and "
        f"{analysis.evidence_quality.research_session_count} fictional research sessions."
    )
    print(
        f"Candidates: {portfolio.candidate_count_before_deduplication} before deduplication; "
        f"{portfolio.candidate_count_after_deduplication} after."
    )
    print(
        f"Portfolio: {len(portfolio.controlled_prototype_ids)} controlled prototype; "
        f"{len(portfolio.further_discovery_ids)} further discovery; "
        f"{len(portfolio.blocked_ids)} blocked."
    )
    evaluation = analysis.benchmark_evaluation
    print(
        f"Top candidate: {top}; benchmark: {evaluation.detected_count}/"
        f"{evaluation.expected_count}; warnings: {len(analysis.warnings)}."
    )
    print(f"Opportunity fingerprint: {analysis.opportunity_analysis_fingerprint}")
    print(f"JSON: {analysis_output}")
    print(f"Markdown: {report_output}")
    print(f"Portfolio: {portfolio_output}")
    print(f"Evidence network: {evidence_output}")
    return 0
