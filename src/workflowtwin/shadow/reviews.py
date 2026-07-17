"""External review validation and isolated deterministic benchmark reviewer."""

from datetime import timedelta
from pathlib import Path
from random import Random

from pydantic import TypeAdapter

from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.fingerprint import shadow_fingerprint, shadow_id
from workflowtwin.shadow.intake import _load_jsonl
from workflowtwin.shadow.models import (
    Recommendation,
    RecommendationStatus,
    ReviewDecision,
    ReviewDecisionType,
    ShadowEvaluationLabel,
    ShadowLabelStatus,
)
from workflowtwin.shadow.oracle import ShadowEvaluationOracle

_REVIEWS = TypeAdapter(tuple[ReviewDecision, ...])


def load_reviews(path: Path) -> tuple[ReviewDecision, ...]:
    return _REVIEWS.validate_python(_load_jsonl(path))


def validate_reviews(
    reviews: tuple[ReviewDecision, ...],
    recommendations: tuple[Recommendation, ...],
    config: ShadowConfig,
) -> tuple[ReviewDecision, ...]:
    versions: dict[tuple[str, int], Recommendation] = {}
    for recommendation in recommendations:
        versions[(recommendation.recommendation_id, recommendation.lifecycle_version)] = (
            recommendation
        )
    seen_reviews: set[str] = set()
    seen_recommendations: set[str] = set()
    for review in reviews:
        if not review.is_synthetic:
            raise ValueError("shadow review data must be explicitly fictional")
        if review.review_id in seen_reviews or review.recommendation_id in seen_recommendations:
            raise ValueError("duplicate review decision")
        seen_reviews.add(review.review_id)
        seen_recommendations.add(review.recommendation_id)
        matched_recommendation = versions.get(
            (review.recommendation_id, review.recommendation_lifecycle_version)
        )
        if matched_recommendation is None:
            raise ValueError(f"recommendation does not exist: {review.recommendation_id}")
        if review.case_id != matched_recommendation.case_id:
            raise ValueError("review case does not match recommendation")
        if review.reviewer_role not in config.reviewer_roles:
            raise ValueError("reviewer role is not permitted")
        if review.decided_at < matched_recommendation.recommendation_at:
            raise ValueError("review cannot occur before recommendation")
        if review.decided_at > matched_recommendation.expires_at and review.decision not in {
            ReviewDecisionType.EXPIRED_BEFORE_REVIEW,
            ReviewDecisionType.NOT_REVIEWED,
        }:
            raise ValueError("expired recommendation must be handled explicitly")
    return tuple(sorted(reviews, key=lambda item: (item.decided_at, item.review_id)))


def benchmark_reviews(
    recommendations: tuple[Recommendation, ...],
    labels: tuple[ShadowEvaluationLabel, ...],
    config: ShadowConfig,
    *,
    seed: int = 42,
) -> tuple[ReviewDecision, ...]:
    """Simulate fictional feedback; hidden labels never enter the detector boundary."""
    oracle = ShadowEvaluationOracle(labels)
    reviewable: dict[str, Recommendation] = {}
    terminal: dict[str, Recommendation] = {}
    for item in recommendations:
        if item.status in {RecommendationStatus.CREATED, RecommendationStatus.UPDATED}:
            reviewable[item.recommendation_id] = item
        elif item.status in {RecommendationStatus.RETRACTED, RecommendationStatus.EXPIRED}:
            terminal[item.recommendation_id] = item
    reviews: list[ReviewDecision] = []
    for recommendation_id, recommendation in sorted(reviewable.items()):
        rng = Random(
            int(
                shadow_fingerprint(
                    {"seed": seed, "recommendation_id": recommendation_id, "purpose": "review"}
                )[:16],
                16,
            )
        )
        label = oracle.label_at(recommendation.case_id, recommendation.recommendation_at)
        delay_minutes = rng.uniform(20, 260)
        decided_at = recommendation.recommendation_at + timedelta(minutes=delay_minutes)
        closure = terminal.get(recommendation_id)
        if (
            closure
            and closure.status is RecommendationStatus.RETRACTED
            and closure.recommendation_at <= decided_at
        ):
            decision = ReviewDecisionType.ALREADY_RESOLVED
            useful = False
            required = label is ShadowLabelStatus.POSITIVE
        elif decided_at > recommendation.expires_at:
            decision = ReviewDecisionType.EXPIRED_BEFORE_REVIEW
            useful = None
            required = label is ShadowLabelStatus.POSITIVE
        elif label is ShadowLabelStatus.POSITIVE:
            decision = (
                ReviewDecisionType.UNCERTAIN if rng.random() < 0.06 else ReviewDecisionType.AGREE
            )
            useful = decision is ReviewDecisionType.AGREE
            required = True
        elif label is ShadowLabelStatus.NEGATIVE:
            decision = (
                ReviewDecisionType.AGREE if rng.random() < 0.04 else ReviewDecisionType.DISAGREE
            )
            useful = False
            required = False
        else:
            decision = ReviewDecisionType.INSUFFICIENT_CONTEXT
            useful = None
            required = None
        reviews.append(
            ReviewDecision(
                review_id=shadow_id("review", config.shadow_run_id, recommendation_id),
                recommendation_id=recommendation_id,
                recommendation_lifecycle_version=recommendation.lifecycle_version,
                case_id=recommendation.case_id,
                reviewer_id=shadow_id("fictional-reviewer", recommendation.case_id, length=10),
                reviewer_role=config.reviewer_roles[0],
                decided_at=decided_at,
                decision=decision,
                reason_codes=("benchmark_reviewer_v1",),
                recommendation_useful=useful,
                completeness_review_required=required,
                arrived_in_time=decided_at <= recommendation.expires_at,
                override_or_correction=decision is ReviewDecisionType.DISAGREE,
                review_duration_minutes=rng.uniform(2, 7),
                decision_source="deterministic_benchmark_only",
            )
        )
    return validate_reviews(tuple(reviews), recommendations, config)
