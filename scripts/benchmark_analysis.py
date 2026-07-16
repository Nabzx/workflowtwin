"""Measure deterministic local analysis performance without asserting machine limits."""

import argparse
import json
import tempfile
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.models import AnalysisInput
from workflowtwin.analytics.reporting import write_analysis_artifacts
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


def benchmark(preset: GenerationPreset) -> dict[str, int | float | str]:
    """Generate outside the timer, then measure analysis and output serialization."""
    generation_config = config_for_preset(preset, seed=42)
    dataset = SyntheticReferralGenerator(
        generation_config,
        generated_at=datetime(2026, 7, 16, 12, tzinfo=UTC),
    ).generate()
    analysis_input = AnalysisInput(
        dataset.cases,
        dataset.events,
        dataset.manifest.dataset_fingerprint,
        dataset.manifest.generation_run_id,
        dataset.manifest,
        dataset.ground_truth,
    )
    config = AnalysisConfig(
        analysis_id=f"northstar-{preset.value}-benchmark",
        source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
        generation_run_id=dataset.manifest.generation_run_id,
    )
    with tempfile.TemporaryDirectory(prefix=f"workflowtwin-{preset.value}-") as directory:
        output_directory = Path(directory)
        analysis_path = output_directory / "analysis.json"
        report_path = output_directory / "report.md"
        cases_path = output_directory / "cases.jsonl"
        started = perf_counter()
        bundle = BaselineAnalyzer(config).analyze(
            analysis_input,
            analysed_at=datetime(2026, 7, 16, 13, tzinfo=UTC),
        )
        analysis_seconds = perf_counter() - started
        write_analysis_artifacts(
            bundle,
            analysis_output=analysis_path,
            report_output=report_path,
            case_metrics_output=cases_path,
        )
        total_seconds = perf_counter() - started
        finding_count = len(bundle.baseline.findings)
        fingerprint = bundle.baseline.analysis_fingerprint
        del bundle
        tracemalloc.start()
        memory_started = perf_counter()
        BaselineAnalyzer(config).analyze(analysis_input)
        memory_profile_seconds = perf_counter() - memory_started
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return {
            "preset": preset.value,
            "case_count": len(dataset.cases),
            "event_count": len(dataset.events),
            "analysis_seconds": round(analysis_seconds, 3),
            "analysis_and_write_seconds": round(total_seconds, 3),
            "traced_peak_memory_mib": round(peak_bytes / 1024 / 1024, 1),
            "memory_profile_seconds": round(memory_profile_seconds, 3),
            "analysis_json_bytes": analysis_path.stat().st_size,
            "report_markdown_bytes": report_path.stat().st_size,
            "case_jsonl_bytes": cases_path.stat().st_size,
            "finding_count": finding_count,
            "analysis_fingerprint": fingerprint,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preset",
        action="append",
        choices=list(GenerationPreset),
        dest="presets",
    )
    arguments = parser.parse_args()
    presets = arguments.presets or list(GenerationPreset)
    for selected in presets:
        print(json.dumps(benchmark(GenerationPreset(selected)), sort_keys=True))


if __name__ == "__main__":
    main()
