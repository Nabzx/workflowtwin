"""Benchmark deterministic opportunity identification on existing demo artifacts."""

import argparse
import json
import tempfile
import tracemalloc
from pathlib import Path
from time import perf_counter

from workflowtwin.opportunities.analyzer import OpportunityIdentifier
from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.reporting import write_opportunity_artifacts
from workflowtwin.services.opportunity_analysis import load_opportunity_input

BenchmarkResult = dict[str, int | float | str]


def benchmark(
    *,
    baseline_path: Path,
    process_path: Path,
    research_path: Path,
    manifest_path: Path | None,
    ground_truth_path: Path | None,
) -> BenchmarkResult:
    """Measure analysis and serialization without asserting machine-specific limits."""
    config = OpportunityConfig(analysis_id="northstar-opportunity-benchmark")
    analysis_input = load_opportunity_input(
        baseline_path=baseline_path,
        process_path=process_path,
        research_path=research_path,
        manifest_path=manifest_path,
        ground_truth_path=ground_truth_path,
        config=config,
    )

    tracemalloc.start()
    started = perf_counter()
    analysis = OpportunityIdentifier(config).analyze(analysis_input)
    analysis_seconds = perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    with tempfile.TemporaryDirectory(prefix="workflowtwin-opportunities-") as directory:
        output = Path(directory)
        analysis_path = output / "analysis.json"
        report_path = output / "report.md"
        portfolio_path = output / "portfolio.json"
        evidence_path = output / "evidence.json"
        write_opportunity_artifacts(
            analysis,
            analysis_output=analysis_path,
            report_output=report_path,
            portfolio_output=portfolio_path,
            evidence_output=evidence_path,
            overwrite=False,
        )
        total_seconds = perf_counter() - started
        portfolio = analysis.portfolio
        evaluation = analysis.benchmark_evaluation
        return {
            "evidence_record_count": analysis.evidence_quality.total_evidence_count,
            "research_session_count": analysis.evidence_quality.research_session_count,
            "raw_candidate_count": portfolio.candidate_count_before_deduplication,
            "candidate_count": portfolio.candidate_count_after_deduplication,
            "controlled_prototype_count": len(portfolio.controlled_prototype_ids),
            "further_discovery_count": len(portfolio.further_discovery_ids),
            "blocked_count": len(portfolio.blocked_ids),
            "analysis_seconds": round(analysis_seconds, 3),
            "analysis_and_write_seconds": round(total_seconds, 3),
            "traced_peak_memory_mib": round(peak_bytes / 1024 / 1024, 1),
            "analysis_json_bytes": analysis_path.stat().st_size,
            "report_markdown_bytes": report_path.stat().st_size,
            "portfolio_json_bytes": portfolio_path.stat().st_size,
            "evidence_network_json_bytes": evidence_path.stat().st_size,
            "benchmark_detection": f"{evaluation.detected_count}/{evaluation.expected_count}",
            "opportunity_analysis_fingerprint": (analysis.opportunity_analysis_fingerprint),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline-analysis",
        type=Path,
        default=Path("artifacts/analysis/demo-analysis.json"),
    )
    parser.add_argument(
        "--process-analysis",
        type=Path,
        default=Path("artifacts/process/demo-process-analysis.json"),
    )
    parser.add_argument(
        "--research-pack",
        type=Path,
        default=Path("data/research/northstar-research-v1.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/generation/northstar-demo-42-manifest.json"),
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("artifacts/generation/northstar-demo-42-ground-truth.json"),
    )
    arguments = parser.parse_args()
    result = benchmark(
        baseline_path=arguments.baseline_analysis,
        process_path=arguments.process_analysis,
        research_path=arguments.research_pack,
        manifest_path=arguments.manifest,
        ground_truth_path=arguments.ground_truth,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
