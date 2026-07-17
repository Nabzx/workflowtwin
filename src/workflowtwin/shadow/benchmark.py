"""Fixed profile comparison for fictional shadow-mode evaluation."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from workflowtwin.shadow.config import DetectorProfile, ShadowConfig
from workflowtwin.shadow.models import (
    IncomingReferralSnapshot,
    ShadowEvaluation,
    ShadowEvaluationLabel,
    ShadowRun,
)
from workflowtwin.shadow.quality import evaluate_shadow
from workflowtwin.shadow.reviews import benchmark_reviews
from workflowtwin.shadow.runner import ShadowModeRunner


@dataclass(frozen=True, slots=True)
class ProfileBenchmark:
    profile: DetectorProfile
    run: ShadowRun
    evaluation: ShadowEvaluation
    runtime_seconds: float


def _comparison_row(evaluation: ShadowEvaluation) -> dict[str, Any]:
    return {
        "profile": evaluation.run_manifest.detector_profile.value,
        "incoming_cases": evaluation.detector.incoming_cases,
        "recommendations": evaluation.detector.recommendations,
        "coverage": evaluation.detector.recommendation_coverage.value,
        "abstention_rate": evaluation.detector.abstention_rate.value,
        "precision": evaluation.detector.precision.value,
        "recall": evaluation.detector.recall.value,
        "false_positive_rate": evaluation.detector.false_positive_rate.value,
        "false_positive_hours": evaluation.burden.false_positive_review_hours,
        "p95_recommendation_latency_minutes": (
            evaluation.source_to_recommendation_latency.p95_minutes
        ),
        "revisions": evaluation.run_manifest.revisions,
        "retractions": evaluation.run_manifest.retractions,
        "promotion_assessment": evaluation.promotion_assessment.result,
    }


def benchmark_profiles(
    *,
    base_config: ShadowConfig,
    snapshots: tuple[IncomingReferralSnapshot, ...],
    labels: tuple[ShadowEvaluationLabel, ...],
    profiles: tuple[DetectorProfile, ...] = (
        DetectorProfile.STRICT,
        DetectorProfile.BALANCED,
        DetectorProfile.EXPLORATORY,
    ),
    reviewer_seed: int = 42,
) -> tuple[ProfileBenchmark, ...]:
    preliminary: list[ProfileBenchmark] = []
    for profile in profiles:
        config = base_config.model_copy(
            update={
                "shadow_run_id": f"{base_config.shadow_run_id}-{profile.value}",
                "detector_profile": profile,
            }
        )
        started = perf_counter()
        run = ShadowModeRunner(config).run(snapshots)
        runtime = perf_counter() - started
        reviews = benchmark_reviews(run.recommendations, labels, config, seed=reviewer_seed)
        evaluation = evaluate_shadow(
            run=run,
            snapshots=snapshots,
            labels=labels,
            reviews=reviews,
            config=config,
            detector_runtime_seconds=runtime,
        )
        preliminary.append(ProfileBenchmark(profile, run, evaluation, runtime))
    comparison = tuple(_comparison_row(item.evaluation) for item in preliminary)
    completed = []
    for item in preliminary:
        config = ShadowConfig.model_validate(item.run.config)
        reviews = benchmark_reviews(item.run.recommendations, labels, config, seed=reviewer_seed)
        evaluation = evaluate_shadow(
            run=item.run,
            snapshots=snapshots,
            labels=labels,
            reviews=reviews,
            config=config,
            detector_runtime_seconds=item.runtime_seconds,
            profile_comparison=comparison,
        )
        completed.append(ProfileBenchmark(item.profile, item.run, evaluation, item.runtime_seconds))
    return tuple(completed)
