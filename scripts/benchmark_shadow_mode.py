"""Benchmark recommendation-only shadow mode on fixed fictional datasets."""

from __future__ import annotations

import argparse
import json
import resource
from pathlib import Path

from workflowtwin.shadow.benchmark import benchmark_profiles
from workflowtwin.shadow.config import DetectorProfile, ShadowConfig
from workflowtwin.shadow.intake import generate_intake_artifacts
from workflowtwin.shadow.reporting import write_evaluation_artifacts
from workflowtwin.synthetic.artifacts import load_dataset


def _fingerprint(path: Path, key: str) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{path} does not contain {key}")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("artifacts/generation/demo-dataset.json")
    )
    parser.add_argument(
        "--opportunity-analysis",
        type=Path,
        default=Path("artifacts/opportunities/demo-opportunities.json"),
    )
    parser.add_argument(
        "--simulation-analysis",
        type=Path,
        default=Path("artifacts/simulation/demo-central.json"),
    )
    parser.add_argument("--strict-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/shadow"))
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    dataset = load_dataset(args.dataset)
    snapshots, labels = generate_intake_artifacts(dataset)
    config = ShadowConfig(
        shadow_run_id=f"{dataset.manifest.generation_run_id}-shadow-benchmark",
        source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
        generation_run_id=dataset.manifest.generation_run_id,
        opportunity_analysis_fingerprint=_fingerprint(
            args.opportunity_analysis, "opportunity_analysis_fingerprint"
        ),
        simulation_analysis_fingerprint=_fingerprint(
            args.simulation_analysis, "simulation_analysis_fingerprint"
        ),
    )
    profiles = (DetectorProfile.STRICT,) if args.strict_only else tuple(DetectorProfile)
    results = benchmark_profiles(
        base_config=config,
        snapshots=snapshots,
        labels=labels,
        profiles=profiles,
    )
    peak_memory_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    for result in results:
        evaluation = result.evaluation
        stem = f"{dataset.manifest.generation_run_id}-{result.profile.value}"
        write_evaluation_artifacts(
            evaluation,
            evaluation_output=args.output_dir / f"{stem}-evaluation.json",
            report_output=args.output_dir / f"{stem}-report.md",
            visualisation_output=args.output_dir / f"{stem}-visualisation.json",
            overwrite=args.force,
        )
        throughput = len(snapshots) / result.runtime_seconds if result.runtime_seconds else 0
        output_paths = (
            args.output_dir / f"{stem}-evaluation.json",
            args.output_dir / f"{stem}-report.md",
            args.output_dir / f"{stem}-visualisation.json",
        )
        output_bytes = sum(path.stat().st_size for path in output_paths)
        checkpoint_bytes = len(result.run.checkpoint.model_dump_json().encode("utf-8"))
        print(
            f"{result.profile.value}: cases={evaluation.detector.incoming_cases}; "
            f"recommendations={evaluation.detector.recommendations}; "
            f"precision={evaluation.detector.precision.value}; "
            f"recall={evaluation.detector.recall.value}; "
            f"fp_hours={evaluation.burden.false_positive_review_hours:.3f}; "
            f"runtime={result.runtime_seconds:.3f}s; throughput={throughput:.1f} items/s; "
            f"assessment={evaluation.promotion_assessment.result}; "
            f"fingerprint={evaluation.evaluation_fingerprint}"
        )
        print(
            f"  source_items={result.run.manifest.source_items_processed}; "
            f"abstentions={evaluation.detector.abstentions}; "
            f"tp/fp/fn={evaluation.detector.true_positives}/"
            f"{evaluation.detector.false_positives}/{evaluation.detector.false_negatives}; "
            f"reviews={evaluation.reviewer.review_count}; "
            f"audit_records={evaluation.audit.total_records}; "
            f"audit_completeness={evaluation.audit.audit_completeness_rate}; "
            f"policy_violations={evaluation.policy.total_policy_violations}; "
            f"p50/p95_latency={evaluation.source_to_recommendation_latency.median_minutes}/"
            f"{evaluation.source_to_recommendation_latency.p95_minutes} logical minutes; "
            f"checkpoint={checkpoint_bytes} bytes; outputs={output_bytes} bytes"
        )
    print(f"Snapshots={len(snapshots)}; approximate peak process memory={peak_memory_mib:.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
