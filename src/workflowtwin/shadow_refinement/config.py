"""Locked strict-v2 and fictional reviewer-capacity configuration."""

from datetime import timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from workflowtwin.domain.referrals.enums import SourceSystem
from workflowtwin.shadow_refinement.fingerprint import locked_fingerprint


class DetectorVersion(StrEnum):
    STRICT_V1 = "strict-v1"
    STRICT_V2 = "strict-v2"
    BALANCED_V1 = "balanced-v1"


class CapacityProfile(StrEnum):
    UNLIMITED = "unlimited"
    CONSTRAINED = "constrained"
    STANDARD = "standard"
    STRESS = "stress"


class OverflowPolicy(StrEnum):
    DEFER = "defer"
    OBSERVE_ONLY = "observe_only"
    EXPIRE = "expire"
    STOP_RUN = "stop_run"


class StrictV2Config(BaseModel):
    """Pre-registered rules; a content change creates a different fingerprint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detector_version: DetectorVersion = DetectorVersion.STRICT_V2
    rule_version: str = "strict-v2-rules-1"
    policy_version: str = "shadow-policy-v1"
    confirmation_window: timedelta = timedelta(minutes=120)
    supported_form_versions: tuple[str, ...] = ("NS-INTAKE-2",)
    supported_source_systems: tuple[SourceSystem, ...] = (
        SourceSystem.REFERRAL_PORTAL,
        SourceSystem.SECURE_EMAIL,
        SourceSystem.MANUAL_ENTRY,
    )
    minimum_evidence_strength: int = Field(default=2, ge=1, le=3)
    require_explicit_absence: bool = True
    suppress_overlapping_source_warning: bool = True
    observe_only_when_review_started: bool = True
    abstain_on_conflict: bool = True
    recommendation_expiry: timedelta = timedelta(hours=8)
    rule_lock_version: str = "2026-07-18.1"

    @property
    def detector_fingerprint(self) -> str:
        return locked_fingerprint(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def enforce_locked_version(self) -> "StrictV2Config":
        if self.detector_version is not DetectorVersion.STRICT_V2:
            raise ValueError("StrictV2Config must use strict-v2")
        return self


class ReviewerCapacityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: CapacityProfile
    capacity_policy_version: str = "review-capacity-v1"
    reviewers_available: int = Field(ge=1)
    review_minutes_available_per_day: float = Field(gt=0)
    review_minutes_per_recommendation: float = Field(default=4.0, gt=0)
    maximum_active_queue_size: int = Field(ge=1)
    maximum_recommendations_per_day: int = Field(ge=1)
    review_slo: timedelta = timedelta(hours=4)
    operating_start_hour: int = Field(default=8, ge=0, le=23)
    operating_end_hour: int = Field(default=18, ge=1, le=24)
    weekends_enabled: bool = False
    reserve_capacity_rate: float = Field(default=0.1, ge=0, lt=1)
    maximum_backlog_age: timedelta = timedelta(hours=24)
    maximum_deferred_age: timedelta = timedelta(hours=12)
    overflow_policy: OverflowPolicy = OverflowPolicy.DEFER

    @property
    def capacity_fingerprint(self) -> str:
        return locked_fingerprint(self.model_dump(mode="json"))

    @property
    def daily_review_slots(self) -> int:
        minutes = self.review_minutes_available_per_day * (1 - self.reserve_capacity_rate)
        return min(
            self.maximum_recommendations_per_day,
            int(minutes // self.review_minutes_per_recommendation),
        )


CAPACITY_CONFIGS = {
    CapacityProfile.UNLIMITED: ReviewerCapacityConfig(
        profile=CapacityProfile.UNLIMITED,
        reviewers_available=100,
        review_minutes_available_per_day=100_000,
        maximum_active_queue_size=100_000,
        maximum_recommendations_per_day=100_000,
        reserve_capacity_rate=0,
        weekends_enabled=True,
    ),
    CapacityProfile.CONSTRAINED: ReviewerCapacityConfig(
        profile=CapacityProfile.CONSTRAINED,
        reviewers_available=2,
        review_minutes_available_per_day=192,
        maximum_active_queue_size=50,
        maximum_recommendations_per_day=43,
        reserve_capacity_rate=0.1,
    ),
    CapacityProfile.STANDARD: ReviewerCapacityConfig(
        profile=CapacityProfile.STANDARD,
        reviewers_available=3,
        review_minutes_available_per_day=288,
        maximum_active_queue_size=75,
        maximum_recommendations_per_day=64,
        reserve_capacity_rate=0.1,
    ),
    CapacityProfile.STRESS: ReviewerCapacityConfig(
        profile=CapacityProfile.STRESS,
        reviewers_available=1,
        review_minutes_available_per_day=96,
        maximum_active_queue_size=25,
        maximum_recommendations_per_day=21,
        reserve_capacity_rate=0.1,
        maximum_backlog_age=timedelta(hours=12),
        maximum_deferred_age=timedelta(hours=6),
    ),
}
