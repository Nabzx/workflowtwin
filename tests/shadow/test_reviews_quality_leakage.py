"""Review validation, hidden labels, metrics, and leakage protections."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from workflowtwin.shadow import detector as detector_module
from workflowtwin.shadow.benchmark import benchmark_profiles
from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.models import (
    IncomingReferralSnapshot,
    ReviewDecision,
    ShadowEvaluationLabel,
    ShadowLabelStatus,
)
from workflowtwin.shadow.quality import evaluate_shadow
from workflowtwin.shadow.reviews import benchmark_reviews, validate_reviews
from workflowtwin.shadow.runner import ShadowModeRunner
from workflowtwin.synthetic.models import GeneratedDataset

ShadowSource = tuple[
    GeneratedDataset,
    tuple[IncomingReferralSnapshot, ...],
    tuple[ShadowEvaluationLabel, ...],
]


def test_hidden_labels_do_not_change_detector_output(
    tiny_shadow_source: ShadowSource, strict_shadow_config: ShadowConfig
) -> None:
    _, snapshots, labels = tiny_shadow_source
    runner = ShadowModeRunner(strict_shadow_config)
    first = runner.run(snapshots)
    changed_labels = tuple(
        label.model_copy(
            update={
                "status": (
                    ShadowLabelStatus.NEGATIVE
                    if label.status is ShadowLabelStatus.POSITIVE
                    else ShadowLabelStatus.POSITIVE
                )
            }
        )
        for label in labels
    )
    second = runner.run(snapshots)
    assert changed_labels != labels
    assert first.recommendations == second.recommendations
    assert first.detector_results == second.detector_results
    assert not hasattr(detector_module, "ShadowEvaluationOracle")


def test_benchmark_reviews_and_metrics_use_correct_denominators(
    tiny_shadow_source: ShadowSource, strict_shadow_config: ShadowConfig
) -> None:
    _, snapshots, labels = tiny_shadow_source
    run = ShadowModeRunner(strict_shadow_config).run(snapshots)
    reviews = benchmark_reviews(run.recommendations, labels, strict_shadow_config)
    evaluation = evaluate_shadow(
        run=run,
        snapshots=snapshots,
        labels=labels,
        reviews=reviews,
        config=strict_shadow_config,
    )
    detector = evaluation.detector
    assert detector.precision.denominator == detector.true_positives + detector.false_positives
    assert detector.recall.denominator == detector.true_positives + detector.false_negatives
    assert detector.abstentions not in {
        detector.true_negatives,
        detector.false_negatives,
    }
    assert evaluation.audit.chain_valid
    assert evaluation.policy.workflow_mutation_attempts == 0
    assert evaluation.source_to_recommendation_latency.p95_minutes == 0
    assert evaluation.evaluation_fingerprint
    repeated = evaluate_shadow(
        run=run,
        snapshots=snapshots,
        labels=labels,
        reviews=reviews,
        config=strict_shadow_config,
        detector_runtime_seconds=999.0,
    )
    assert repeated.evaluation_fingerprint == evaluation.evaluation_fingerprint
    if any(
        item.breached and item.action in {"pause_shadow_run", "stop_shadow_run"}
        for item in evaluation.stop_conditions
    ):
        assert evaluation.promotion_assessment.result == "pause_due_to_stop_condition"


def test_no_ground_truth_leaves_quality_metrics_unavailable(
    tiny_shadow_source: ShadowSource, strict_shadow_config: ShadowConfig
) -> None:
    _, snapshots, _ = tiny_shadow_source
    run = ShadowModeRunner(strict_shadow_config).run(snapshots)
    evaluation = evaluate_shadow(
        run=run,
        snapshots=snapshots,
        labels=(),
        reviews=(),
        config=strict_shadow_config,
    )
    assert evaluation.detector.precision.value is None
    assert evaluation.detector.recall.value is None
    assert evaluation.detector.unresolved_labels == evaluation.detector.evaluated_cases


def test_review_validation_rejects_invalid_time_duplicate_and_sensitive_comment(
    tiny_shadow_source: ShadowSource, strict_shadow_config: ShadowConfig
) -> None:
    _, snapshots, labels = tiny_shadow_source
    run = ShadowModeRunner(strict_shadow_config).run(snapshots)
    reviews = benchmark_reviews(run.recommendations, labels, strict_shadow_config)
    if not reviews:
        pytest.skip("fixture produced no reviewable recommendation")
    review = reviews[0]
    invalid_time = review.model_copy(
        update={"decided_at": run.recommendations[0].recommendation_at - timedelta(minutes=1)}
    )
    with pytest.raises(ValueError, match="before recommendation"):
        validate_reviews((invalid_time,), run.recommendations, strict_shadow_config)
    with pytest.raises(ValueError, match="duplicate"):
        validate_reviews((review, review), run.recommendations, strict_shadow_config)
    with pytest.raises(ValidationError, match="clinical or identifying"):
        ReviewDecision.model_validate(
            {**review.model_dump(mode="python"), "comment": "contains diagnosis detail"}
        )


def test_profile_comparison_emphasises_strict_and_marks_exploratory(
    tiny_shadow_source: ShadowSource, strict_shadow_config: ShadowConfig
) -> None:
    _, snapshots, labels = tiny_shadow_source
    results = benchmark_profiles(
        base_config=strict_shadow_config,
        snapshots=snapshots,
        labels=labels,
    )
    assert [item.profile.value for item in results] == ["strict", "balanced", "exploratory"]
    assert all(len(item.evaluation.profile_comparison) == 3 for item in results)
    strict, _, exploratory = results
    assert strict.evaluation.detector.abstentions >= 0
    assert exploratory.evaluation.run_manifest.detector_profile.value == "exploratory"
