"""Deterministic A/B benchmark orchestration for fictional Northstar data."""

from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

from workflowtwin.shadow.intake import generate_intake_artifacts, intake_snapshot_fingerprint
from workflowtwin.shadow.models import (
    IncomingReferralSnapshot,
    ShadowEvaluationLabel,
    ShadowLabelStatus,
)
from workflowtwin.shadow_refinement.config import StrictV2Config
from workflowtwin.shadow_refinement.detector import with_confirmation_window
from workflowtwin.shadow_refinement.evaluation import evaluate_v1, evaluate_v2
from workflowtwin.shadow_refinement.fingerprint import locked_fingerprint
from workflowtwin.shadow_refinement.models import (
    BenchmarkDatasetManifest,
    DatasetEvaluation,
    DatasetSpecification,
    RefinementProtocol,
)
from workflowtwin.synthetic.config import GenerationConfig
from workflowtwin.synthetic.generator import SyntheticReferralGenerator

_GENERATED_AT = datetime(2026, 7, 18, tzinfo=UTC)


def build_dataset(
    specification: DatasetSpecification,
) -> tuple[
    BenchmarkDatasetManifest,
    tuple[IncomingReferralSnapshot, ...],
    tuple[ShadowEvaluationLabel, ...],
]:
    """Generate one immutable benchmark split and its separated intake labels."""
    config = GenerationConfig(
        seed=specification.seed,
        case_count=specification.case_count,
        operating_days=specification.operating_days,
        generation_run_id=specification.generation_run_id,
    )
    dataset = SyntheticReferralGenerator(config, generated_at=_GENERATED_AT).generate()
    snapshots, labels = generate_intake_artifacts(dataset)
    initial_labels: dict[UUID, ShadowEvaluationLabel] = {}
    for label in labels:
        initial_labels.setdefault(label.case_id, label)
    source_mix = Counter(
        item.source_system.value for item in snapshots if item.source_record_version == 1
    )
    form_mix = Counter(item.form_version for item in snapshots if item.source_record_version == 1)
    quality: Counter[str] = Counter()
    for snapshot in snapshots:
        if snapshot.is_source_retry:
            quality["source_retry"] += 1
        if snapshot.source_record_version > 1:
            quality["corrected_snapshot"] += 1
    positives = sum(item.status is ShadowLabelStatus.POSITIVE for item in initial_labels.values())
    manifest = BenchmarkDatasetManifest(
        dataset_id=specification.dataset_id,
        role=specification.role,
        seed=specification.seed,
        case_count=specification.case_count,
        dataset_fingerprint=dataset.manifest.dataset_fingerprint,
        snapshot_fingerprint=intake_snapshot_fingerprint(snapshots),
        source_mix=dict(sorted(source_mix.items())),
        form_version_mix=dict(sorted(form_mix.items())),
        positive_prevalence=positives / specification.case_count,
        data_quality_conditions=dict(sorted(quality.items())),
    )
    return manifest, snapshots, labels


def compare_dataset(
    specification: DatasetSpecification,
    protocol: RefinementProtocol,
) -> tuple[DatasetEvaluation, DatasetEvaluation]:
    manifest, snapshots, labels = build_dataset(specification)
    v1 = evaluate_v1(
        manifest=manifest,
        snapshots=snapshots,
        labels=labels,
        thresholds=protocol.thresholds,
    )
    v2 = evaluate_v2(
        manifest=manifest,
        snapshots=snapshots,
        labels=labels,
        config=StrictV2Config(),
        thresholds=protocol.thresholds,
    )
    return v1, v2


def comparison_summary(v1: DatasetEvaluation, v2: DatasetEvaluation) -> dict[str, object]:
    changes = {}
    for metric in (
        "detector_positives",
        "precision",
        "recall",
        "false_positive_review_hours",
        "recommendation_latency_mean_minutes",
    ):
        before = getattr(v1.detector, metric)
        after = getattr(v2.detector, metric)
        changes[metric] = {
            "strict_v1": before,
            "strict_v2": after,
            "absolute_change": after - before
            if isinstance(before, (int, float)) and isinstance(after, (int, float))
            else None,
        }
    result: dict[str, object] = {
        "dataset": v1.dataset.model_dump(mode="json"),
        "strict_v1": v1.model_dump(mode="json", exclude={"queue_events"}),
        "strict_v2": v2.model_dump(mode="json", exclude={"queue_events"}),
        "changes": changes,
    }
    result["comparison_fingerprint"] = locked_fingerprint(result)
    return result


def sensitivity_summary(
    specification: DatasetSpecification, protocol: RefinementProtocol
) -> list[dict[str, object]]:
    """Report nearby pre-declared windows without selecting a new detector."""
    manifest, snapshots, labels = build_dataset(specification)
    results: list[dict[str, object]] = []
    for minutes in (60, 120, 180):
        config = with_confirmation_window(StrictV2Config(), minutes)
        evaluation = evaluate_v2(
            manifest=manifest,
            snapshots=snapshots,
            labels=labels,
            config=config,
            thresholds=protocol.thresholds,
        )
        results.append(
            {
                "confirmation_window_minutes": minutes,
                "detector_fingerprint": config.detector_fingerprint,
                "metrics": evaluation.detector.model_dump(mode="json"),
                "capacity": [item.model_dump(mode="json") for item in evaluation.capacity],
                "selection_status": "report_only_not_selected",
            }
        )
    return results


def pareto_summary(results: list[dict[str, object]]) -> list[dict[str, object]]:
    """Expose quality, latency, and queue burden without a composite score."""
    points = []
    for result in results:
        dataset = result["dataset"]
        evaluation = result["strict_v2"]
        assert isinstance(dataset, dict) and isinstance(evaluation, dict)
        detector = evaluation["detector"]
        capacities = evaluation["capacity"]
        assert isinstance(detector, dict) and isinstance(capacities, list)
        for capacity in capacities:
            assert isinstance(capacity, dict)
            points.append(
                {
                    "dataset_id": dataset["dataset_id"],
                    "capacity_profile": capacity["profile"],
                    "precision": detector["precision"],
                    "recall": detector["recall"],
                    "false_positive_review_hours": detector["false_positive_review_hours"],
                    "recommendation_latency_minutes": detector[
                        "recommendation_latency_mean_minutes"
                    ],
                    "surfaced_coverage": capacity["surfaced_coverage"],
                    "maximum_queue_depth": capacity["maximum_queue_depth"],
                    "is_non_dominated": capacity["profile"] == "unlimited",
                }
            )
    return points
