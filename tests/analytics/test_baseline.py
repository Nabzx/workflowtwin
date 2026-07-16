"""Cohort, quality, finding, evaluation, and fingerprint tests."""

from datetime import UTC, datetime

import pytest

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.fingerprint import dataset_fingerprint
from workflowtwin.analytics.models import AnalysisInput, EvaluationStatus, MetricName
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.models import GeneratedDataset
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


@pytest.fixture(scope="module")
def demo_dataset() -> GeneratedDataset:
    config = config_for_preset(GenerationPreset.DEMO, seed=42)
    return SyntheticReferralGenerator(
        config, generated_at=datetime(2026, 7, 16, 12, tzinfo=UTC)
    ).generate()


def _input(dataset: GeneratedDataset, *, ground_truth: bool = True) -> AnalysisInput:
    return AnalysisInput(
        cases=dataset.cases,
        events=dataset.events,
        dataset_fingerprint=dataset.manifest.dataset_fingerprint,
        generation_run_id=dataset.manifest.generation_run_id,
        manifest=dataset.manifest,
        ground_truth=dataset.ground_truth if ground_truth else None,
    )


def test_demo_analysis_reconciles_counts_and_detects_planted_patterns(
    demo_dataset: GeneratedDataset,
) -> None:
    bundle = BaselineAnalyzer(AnalysisConfig()).analyze(_input(demo_dataset))
    baseline = bundle.baseline

    assert baseline.case_count == 1_000
    assert baseline.overall.case_count == baseline.case_count
    assert baseline.overall.completed_count == sum(
        case.lifecycle_status == "completed" for case in bundle.case_metrics
    )
    terminal_count = sum(baseline.overall.rates[name].denominator for name in ("completion_rate",))
    assert terminal_count == sum(
        case.lifecycle_status in {"completed", "cancelled", "rejected", "closed_other"}
        for case in bundle.case_metrics
    )
    assert baseline.ground_truth_evaluation.detected_count == 4
    assert baseline.ground_truth_evaluation.planted_count == 4
    assert not baseline.ground_truth_evaluation.false_negatives
    assert {
        (finding.cohort_dimension, finding.cohort_value, finding.finding_type)
        for finding in baseline.findings
    }.issuperset(
        {
            ("referral_source", "gp_practice", "lower_first_pass_completeness"),
            ("service_line", "neurology", "longer_assignment_wait"),
            ("service_line", "respiratory", "elevated_failed_scheduling"),
            ("service_line", "dermatology", "elevated_reassignment"),
        }
    )


def test_metric_coverage_matches_case_results(demo_dataset: GeneratedDataset) -> None:
    bundle = BaselineAnalyzer(AnalysisConfig()).analyze(_input(demo_dataset, ground_truth=False))
    quality = bundle.baseline.quality

    for metric_name in MetricName:
        expected = sum(
            case.metrics[metric_name].status.value == "calculated" for case in bundle.case_metrics
        )
        assert quality.metric_status_counts[metric_name.value].get("calculated", 0) == expected
    duration = bundle.baseline.overall.summaries[MetricName.CASE_DURATION.value]
    assert duration.available_count + duration.excluded_count == bundle.baseline.case_count


def test_fingerprint_is_stable_and_changes_with_configuration(
    demo_dataset: GeneratedDataset,
) -> None:
    first = BaselineAnalyzer(AnalysisConfig()).analyze(
        _input(demo_dataset, ground_truth=False),
        analysed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = BaselineAnalyzer(AnalysisConfig()).analyze(
        _input(demo_dataset, ground_truth=False),
        analysed_at=datetime(2027, 1, 1, tzinfo=UTC),
    )
    changed = BaselineAnalyzer(AnalysisConfig(stuck_threshold_hours=96)).analyze(
        _input(demo_dataset, ground_truth=False)
    )

    assert first.baseline.analysis_fingerprint == second.baseline.analysis_fingerprint
    assert first.baseline.analysis_fingerprint != changed.baseline.analysis_fingerprint
    assert first.baseline.analysed_at != second.baseline.analysed_at


def test_no_ground_truth_is_a_clear_non_failure(demo_dataset: GeneratedDataset) -> None:
    baseline = (
        BaselineAnalyzer(AnalysisConfig())
        .analyze(_input(demo_dataset, ground_truth=False))
        .baseline
    )

    assert baseline.ground_truth_evaluation.status is EvaluationStatus.NOT_EVALUATED
    assert baseline.ground_truth_evaluation.planted_count == 0


def test_manifest_and_ground_truth_mismatches_are_rejected(
    demo_dataset: GeneratedDataset,
) -> None:
    actual = dataset_fingerprint(demo_dataset.cases, demo_dataset.events)
    wrong_manifest = demo_dataset.manifest.model_copy(update={"dataset_fingerprint": "0" * 64})
    wrong_truth = demo_dataset.ground_truth.model_copy(update={"run_id": "different-run"})

    with pytest.raises(ValueError, match="manifest dataset fingerprint"):
        BaselineAnalyzer(AnalysisConfig()).analyze(
            AnalysisInput(
                demo_dataset.cases,
                demo_dataset.events,
                actual,
                demo_dataset.manifest.generation_run_id,
                wrong_manifest,
            )
        )
    with pytest.raises(ValueError, match="ground truth generation run"):
        BaselineAnalyzer(AnalysisConfig()).analyze(
            AnalysisInput(
                demo_dataset.cases,
                demo_dataset.events,
                actual,
                demo_dataset.manifest.generation_run_id,
                demo_dataset.manifest,
                wrong_truth,
            )
        )


def test_unsupported_schema_is_excluded_without_breaking_other_cases(
    demo_dataset: GeneratedDataset,
) -> None:
    unsupported = demo_dataset.cases[0].model_copy(update={"schema_version": 2})
    cases = (unsupported, *demo_dataset.cases[1:3])
    case_ids = {case.id for case in cases}
    events = tuple(event for event in demo_dataset.events if event.referral_case_id in case_ids)
    fingerprint = dataset_fingerprint(cases, events)

    baseline = (
        BaselineAnalyzer(AnalysisConfig())
        .analyze(AnalysisInput(cases, events, fingerprint))
        .baseline
    )

    assert baseline.case_count == 2
    assert baseline.quality.unsupported_schema_cases == 1
    assert baseline.quality.cases_excluded_entirely == 1
