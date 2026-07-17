"""Validated configuration for deterministic recommendation shadow runs."""

from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DetectorProfile(StrEnum):
    STRICT = "strict"
    BALANCED = "balanced"
    EXPLORATORY = "exploratory"


class LateDataPolicy(StrEnum):
    APPLY_WITH_WARNING = "apply_with_warning"
    ABSTAIN = "abstain"


class ShadowConfig(BaseModel):
    """One immutable, lineage-bound replay configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    shadow_run_id: str
    shadow_mode_version: str = "1.0.0"
    detector_version: str = "completeness-review-v1"
    policy_version: str = "shadow-policy-v1"
    source_dataset_fingerprint: str
    generation_run_id: str
    opportunity_analysis_fingerprint: str
    simulation_analysis_fingerprint: str
    activity_map_version: str = "northstar-referral-v1"
    snapshot_schema_version: int = 1
    replay_start: datetime | None = None
    replay_end: datetime | None = None
    availability_ordering: str = "available_at,source_type_priority,snapshot_id"
    identical_timestamp_tiebreaker: str = "snapshot_id"
    detector_profile: DetectorProfile = DetectorProfile.STRICT
    confidence_threshold: float = Field(default=0.9, ge=0, le=1)
    abstain_on_ambiguity: bool = True
    recommendation_expiry: timedelta = timedelta(hours=8)
    duplicate_suppression_period: timedelta = timedelta(hours=8)
    late_data_policy: LateDataPolicy = LateDataPolicy.APPLY_WITH_WARNING
    review_slo: timedelta = timedelta(hours=4)
    reviewer_roles: tuple[str, ...] = ("northstar_admin_reviewer",)
    minimum_evaluation_sample: int = Field(default=30, ge=1)
    hidden_label_evaluation_enabled: bool = True
    minimum_precision: float = Field(default=0.9, ge=0, le=1)
    maximum_false_positive_hours_per_100_cases: float = Field(default=0.25, ge=0)
    maximum_recommendation_rate: float = Field(default=0.2, gt=0, le=1)
    maximum_duplicate_rate: float = Field(default=0.01, ge=0, le=1)
    maximum_reviewer_rejection_rate: float = Field(default=0.15, ge=0, le=1)
    maximum_detector_failure_rate: float = Field(default=0.01, ge=0, le=1)
    maximum_unresolved_review_rate: float = Field(default=0.2, ge=0, le=1)
    maximum_p95_recommendation_latency_minutes: float = Field(default=10, gt=0)
    maximum_unsupported_input_rate: float = Field(default=0.1, ge=0, le=1)
    minimum_source_freshness_rate: float = Field(default=0.95, ge=0, le=1)
    minimum_audit_completeness: float = Field(default=1.0, ge=0, le=1)
    administrative_hourly_cost_gbp: float = Field(default=24.0, ge=0)
    estimated_minutes_per_review: float = Field(default=4.0, gt=0)
    recommendations_output: Path | None = None
    audit_output: Path | None = None
    run_output: Path | None = None
    overwrite: bool = False

    @model_validator(mode="after")
    def validate_window_and_profile(self) -> "ShadowConfig":
        if self.replay_start and self.replay_end and self.replay_end < self.replay_start:
            raise ValueError("replay_end cannot be earlier than replay_start")
        if (
            self.detector_profile is DetectorProfile.EXPLORATORY
            and not self.hidden_label_evaluation_enabled
        ):
            raise ValueError("exploratory profile is evaluation-only")
        return self
