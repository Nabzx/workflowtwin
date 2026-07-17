"""Fixed-seed process benchmark and cross-analysis reconciliation."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.process_mining.analyzer import ProcessMiningAnalyzer
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import ProcessMiningBundle
from workflowtwin.process_mining.reporting import (
    ProcessArtifactExistsError,
    write_process_artifacts,
)
from workflowtwin.services.baseline_analysis import input_from_dataset
from workflowtwin.services.process_analysis import process_input_from_dataset
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.models import GeneratedDataset
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


@pytest.fixture(scope="module")
def demo_dataset() -> GeneratedDataset:
    return SyntheticReferralGenerator(
        config_for_preset(GenerationPreset.DEMO, seed=42),
        generated_at=datetime(2026, 7, 16, 12, tzinfo=UTC),
    ).generate()


@pytest.fixture(scope="module")
def demo_bundle(demo_dataset: GeneratedDataset) -> ProcessMiningBundle:
    baseline = (
        BaselineAnalyzer(
            AnalysisConfig(
                source_dataset_fingerprint=demo_dataset.manifest.dataset_fingerprint,
                generation_run_id=demo_dataset.manifest.generation_run_id,
                minimum_cohort_size=20,
            )
        )
        .analyze(input_from_dataset(demo_dataset))
        .baseline
    )
    config = ProcessMiningConfig(
        source_dataset_fingerprint=demo_dataset.manifest.dataset_fingerprint,
        baseline_analysis_fingerprint=baseline.analysis_fingerprint,
        generation_run_id=demo_dataset.manifest.generation_run_id,
    )
    return ProcessMiningAnalyzer(config).analyze(
        process_input_from_dataset(
            demo_dataset,
            baseline=baseline,
            ground_truth=demo_dataset.ground_truth,
        ),
        analysed_at=datetime(2026, 7, 17, tzinfo=UTC),
    )


def test_demo_reconstructs_process_and_detects_planted_patterns(
    demo_bundle: ProcessMiningBundle,
) -> None:
    analysis = demo_bundle.analysis

    assert analysis.case_count == 1_000
    assert analysis.event_count == 10_085
    assert analysis.complexity.distinct_activity_count == 17
    assert analysis.complexity.distinct_transition_count == 23
    assert analysis.complexity.distinct_variant_count == 57
    assert analysis.complexity.top_1_variant_coverage == pytest.approx(0.363)
    assert analysis.complexity.top_5_variant_coverage == pytest.approx(0.67)
    assert analysis.complexity.top_10_variant_coverage == pytest.approx(0.802)
    assert analysis.strict_conformance is not None
    assert analysis.governed_conformance is not None
    assert analysis.strict_conformance.fully_conforming_rate == pytest.approx(0.363)
    assert analysis.governed_conformance.fully_conforming_rate == pytest.approx(0.871)
    assert analysis.ground_truth_evaluation.detected_count == 4
    assert not analysis.ground_truth_evaluation.false_negatives
    assert len(analysis.baseline_reconciliation) >= 4
    assert sum(item.supports_finding for item in analysis.baseline_reconciliation) >= 4
    assert analysis.discovery.pm4py_dfg_matches_canonical


def test_demo_counts_and_candidate_denominators_reconcile(
    demo_bundle: ProcessMiningBundle,
) -> None:
    analysis = demo_bundle.analysis

    assert sum(variant.case_count for variant in analysis.variants) == analysis.case_count
    assert sum(analysis.start_activity_counts.values()) == analysis.case_count
    assert sum(analysis.end_activity_counts.values()) == analysis.case_count
    assert len(analysis.graph_data.nodes) == analysis.complexity.distinct_activity_count
    assert len(analysis.graph_data.edges) == analysis.complexity.distinct_transition_count
    neurology = next(
        item
        for item in analysis.bottleneck_candidates
        if item.candidate_type == "service_line_assignment_delay"
        and item.cohort_value == "neurology"
    )
    assert neurology.case_count == 222
    assert len(neurology.supporting_case_ids) == 25


def test_process_fingerprint_is_stable_and_configuration_sensitive(
    demo_dataset: GeneratedDataset, demo_bundle: ProcessMiningBundle
) -> None:
    process_input = process_input_from_dataset(demo_dataset)
    base = ProcessMiningConfig(
        source_dataset_fingerprint=demo_dataset.manifest.dataset_fingerprint,
        generation_run_id=demo_dataset.manifest.generation_run_id,
    )
    repeated = ProcessMiningAnalyzer(base).analyze(
        process_input, analysed_at=datetime(2030, 1, 1, tzinfo=UTC)
    )
    changed = ProcessMiningAnalyzer(
        base.model_copy(update={"minimum_transition_frequency": 6})
    ).analyze(process_input, analysed_at=datetime(2030, 1, 2, tzinfo=UTC))

    # Baseline input is part of the fingerprint, so compare like-for-like no-baseline runs.
    original = ProcessMiningAnalyzer(base).analyze(
        process_input, analysed_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
    assert repeated.analysis.process_analysis_fingerprint == (
        original.analysis.process_analysis_fingerprint
    )
    assert changed.analysis.process_analysis_fingerprint != (
        original.analysis.process_analysis_fingerprint
    )
    assert demo_bundle.analysis.process_analysis_fingerprint != (
        original.analysis.process_analysis_fingerprint
    )


def test_demo_artifacts_are_machine_and_recruiter_readable(
    tmp_path: Path, demo_bundle: ProcessMiningBundle
) -> None:
    analysis_path = tmp_path / "analysis.json"
    report_path = tmp_path / "report.md"
    graph_path = tmp_path / "graph.json"
    case_path = tmp_path / "cases.jsonl"

    write_process_artifacts(
        demo_bundle,
        analysis_output=analysis_path,
        report_output=report_path,
        graph_output=graph_path,
        case_output=case_path,
        overwrite=False,
    )

    analysis = json.loads(analysis_path.read_text())
    graph = json.loads(graph_path.read_text())
    markdown = report_path.read_text()
    assert analysis["process_analysis_fingerprint"] == (
        demo_bundle.analysis.process_analysis_fingerprint
    )
    assert len(graph["nodes"]) == 17
    assert "Strict versus governed conformance" in markdown
    assert "Most common deviations" in markdown
    assert "all process records" in markdown
    assert len(case_path.read_text().splitlines()) == 1_000

    with pytest.raises(ProcessArtifactExistsError):
        write_process_artifacts(
            demo_bundle,
            analysis_output=analysis_path,
            report_output=report_path,
            graph_output=graph_path,
            case_output=case_path,
            overwrite=False,
        )
