"""Typed refinement, priority, queue, diagnostic, and comparison contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from workflowtwin.shadow_refinement.config import CapacityProfile, DetectorVersion


class RefinementModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DatasetRole(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    HOLDOUT = "holdout"


class DatasetSpecification(RefinementModel):
    dataset_id: str
    role: DatasetRole
    seed: int
    case_count: int = Field(ge=1)
    operating_days: int = Field(default=180, ge=1)
    generation_run_id: str


class BenchmarkDatasetManifest(RefinementModel):
    dataset_id: str
    role: DatasetRole
    seed: int
    case_count: int
    dataset_fingerprint: str
    snapshot_fingerprint: str
    source_mix: dict[str, int]
    form_version_mix: dict[str, int]
    positive_prevalence: float
    data_quality_conditions: dict[str, int]


class RefinementThresholds(RefinementModel):
    capacity_threshold: float = Field(default=0.2, gt=0, le=1)
    minimum_precision: float = Field(default=0.9, ge=0, le=1)
    minimum_recall: float = Field(default=0.72, ge=0, le=1)
    maximum_false_positive_hours_per_100_cases: float = Field(default=0.25, ge=0)
    maximum_precision_drop: float = Field(default=0.03, ge=0)
    maximum_recall_drop: float = Field(default=0.08, ge=0)
    minimum_cohort_sample: int = Field(default=30, ge=1)


class RefinementProtocol(RefinementModel):
    protocol_id: str
    protocol_version: str
    development_datasets: tuple[DatasetSpecification, ...]
    validation_datasets: tuple[DatasetSpecification, ...]
    holdout_dataset: DatasetSpecification
    base_detector_version: DetectorVersion
    candidate_detector_version: DetectorVersion
    reviewer_seed: int
    permitted_refinement_dimensions: tuple[str, ...]
    frozen_metrics: tuple[str, ...]
    thresholds: RefinementThresholds
    rule_lock_version: str
    holdout_evaluated: bool = False
    holdout_evaluation_count: int = 0


class RefinementContext(RefinementModel):
    snapshot_id: str
    source_warning_codes: tuple[str, ...] = ()
    manual_review_started: bool | None = None
    conflicting_source_state: bool = False
    source_freshness_minutes: float = 0


class ConfirmationStatus(StrEnum):
    PENDING = "confirmation_pending"
    CONFIRMED = "concern_confirmed"
    RESOLVED = "concern_resolved_during_window"
    INELIGIBLE = "became_ineligible"


class PriorityLevel(StrEnum):
    ADMINISTRATIVE_HIGH = "high_administrative_review"
    STANDARD = "standard_administrative_review"
    LOW = "low_priority_review"
    OBSERVE_ONLY = "observe_only"
    ABSTAIN = "abstain"


class RefinedSignal(RefinementModel):
    signal_id: str
    case_id: UUID
    detector_version: DetectorVersion
    rule_id: str
    detected_at: datetime
    confirmation_due_at: datetime
    decided_at: datetime
    status: ConfirmationStatus
    reason_codes: tuple[str, ...]
    source_snapshot_ids: tuple[str, ...]
    evidence_strength: int
    priority: PriorityLevel
    priority_reasons: tuple[str, ...]
    source_warning_overlap: bool
    manual_review_started: bool | None
    additional_latency_minutes: float
    audit_reference: str


class QueueStatus(StrEnum):
    ACTIVE = "active"
    QUEUED = "queued"
    ASSIGNED = "assigned_for_review"
    DEFERRED = "deferred"
    SURFACED = "surfaced"
    OBSERVE_ONLY = "observe_only"
    EXPIRED = "expired_in_queue"
    RETRACTED = "retracted_before_review"
    CLOSED = "closed"
    DROPPED = "dropped_shadow_run_stopped"


class QueueEvent(RefinementModel):
    queue_event_id: str
    signal_id: str
    case_id: UUID
    occurred_at: datetime
    sequence_number: int
    status: QueueStatus
    priority: PriorityLevel
    reason_codes: tuple[str, ...]
    queue_depth: int
    queue_age_minutes: float
    capacity_profile: CapacityProfile
    capacity_fingerprint: str
    audit_reference: str
    content_fingerprint: str


class QueueCheckpoint(RefinementModel):
    run_id: str
    source_position: int
    detector_fingerprint: str
    capacity_fingerprint: str
    pending_confirmations: tuple[RefinedSignal, ...]
    queue_events: tuple[QueueEvent, ...]
    active_signal_ids: tuple[str, ...]
    audit_root: str | None
    checkpoint_fingerprint: str


class RulePerformance(RefinementModel):
    reason_key: str
    detector_evaluations: int
    recommendations: int
    evaluable_recommendations: int
    true_positives: int
    false_positives: int
    unresolved_labels: int
    precision: float | None
    recall_contribution: float | None
    false_positive_review_hours: float
    total_review_hours: float
    reviewer_agreement: float | None
    useful_and_correct_rate: float | None
    correct_but_redundant_rate: float | None
    incorrect_rate: float | None
    already_resolved_rate: float | None
    retraction_rate: float | None
    average_recommendation_latency_minutes: float | None
    source_system_distribution: dict[str, int]
    form_version_distribution: dict[str, int]
    cohort_sample_size: int
    weekly_precision: tuple[float | None, ...]


class RootCause(RefinementModel):
    case_id: UUID
    recommendation_id: str
    primary_category: str
    secondary_categories: tuple[str, ...]
    source_references: tuple[str, ...]
    mitigable_as_of_time: bool
    introduces_latency: bool
    may_reduce_recall: bool


class CapacityMetrics(RefinementModel):
    profile: CapacityProfile
    incoming_cases: int
    detector_positive_cases: int
    active_recommendations: int
    surfaced_recommendations: int
    reviewed_recommendations: int
    queued_recommendations: int
    deferred_recommendations: int
    observe_only_signals: int
    expired_in_queue: int
    detector_positive_coverage: float
    active_recommendation_coverage: float
    surfaced_coverage: float
    reviewed_coverage: float
    observe_only_coverage: float
    maximum_queue_depth: int
    maximum_backlog_age_minutes: float
    mean_queue_delay_minutes: float | None
    p95_queue_delay_minutes: float | None
    capacity_utilisation: float


class DetectorMetrics(RefinementModel):
    detector_version: DetectorVersion
    incoming_cases: int
    detector_positives: int
    abstentions: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    unresolved: int
    precision: float | None
    recall: float | None
    specificity: float | None
    false_positive_rate: float | None
    false_positive_review_hours: float
    recommendation_latency_mean_minutes: float | None
    recommendation_latency_p95_minutes: float | None
    audit_completeness: float
    policy_compliance: float


class MissedPositive(RefinementModel):
    case_id: UUID
    exclusion_rule: str
    disposition: str
    earlier_recommendation_possible: bool
    eventually_found_by_human: bool
    fictional_operational_consequence: str
    excessive_narrowing_warning: bool


class CohortGuardrail(RefinementModel):
    dimension: str
    value: str
    sample_size: int
    detector_positives: int
    surfaced_recommendations: int
    precision: float | None
    recall: float | None
    false_positive_review_hours: float
    abstentions: int
    mean_queue_delay_minutes: float | None
    reviewer_agreement: float | None
    status: str


class ChronologicalWindow(RefinementModel):
    window_id: str
    incoming_cases: int
    detector_positives: int
    surfaced_recommendations: int
    maximum_queue_depth: int
    precision: float | None
    recall: float | None
    false_positive_review_hours: float
    mean_review_latency_minutes: float | None
    expired_recommendations: int
    policy_compliance: float
    stop_condition_breaches: tuple[str, ...]
    interpretation: str


class VersionComparison(RefinementModel):
    metric: str
    strict_v1: float | int | None
    strict_v2: float | int | None
    absolute_change: float | int | None
    classification: str


class ParetoResult(RefinementModel):
    configuration_id: str
    precision: float | None
    recall: float | None
    detector_positive_coverage: float
    surfaced_coverage: float
    false_positive_review_hours: float
    reviewer_agreement: float | None
    recommendation_latency_minutes: float | None
    queue_burden: int
    abstention_rate: float
    is_non_dominated: bool


class DatasetEvaluation(RefinementModel):
    dataset: BenchmarkDatasetManifest
    detector: DetectorMetrics
    capacity: tuple[CapacityMetrics, ...]
    rule_performance: tuple[RulePerformance, ...]
    false_positive_causes: tuple[RootCause, ...]
    redundancy_causes: dict[str, int]
    missed_positives: tuple[MissedPositive, ...]
    cohort_guardrails: tuple[CohortGuardrail, ...]
    chronological_windows: tuple[ChronologicalWindow, ...]
    queue_events: tuple[QueueEvent, ...]
    stop_condition_breaches: tuple[str, ...]
    promotion_gates: dict[str, str]
    promotion_assessment: str
    detector_fingerprint: str
    evaluation_fingerprint: str


class HoldoutRegistry(RefinementModel):
    protocol_id: str
    dataset_id: str
    detector_version: DetectorVersion
    detector_fingerprint: str
    evaluation_count: int
    evaluation_fingerprint: str | None
    status: str


class RefinementAnalysis(RefinementModel):
    protocol: RefinementProtocol
    strict_v2_configuration: dict[str, JsonValue]
    dataset_manifests: tuple[BenchmarkDatasetManifest, ...]
    development_results: tuple[DatasetEvaluation, ...]
    validation_results: tuple[DatasetEvaluation, ...]
    holdout_result: DatasetEvaluation | None
    version_comparison: tuple[VersionComparison, ...]
    capacity_comparison: tuple[dict[str, Any], ...]
    pareto_results: tuple[ParetoResult, ...]
    sensitivity_results: tuple[dict[str, Any], ...]
    accepted_rule_changes: tuple[str, ...]
    rejected_rule_changes: tuple[str, ...]
    warnings: tuple[str, ...]
    refinement_fingerprint: str


class RefinementRunResult(RefinementModel):
    signals: tuple[RefinedSignal, ...]
    queue_events: tuple[QueueEvent, ...]
    audit_records: tuple[dict[str, Any], ...]
    checkpoint: QueueCheckpoint
    run_fingerprint: str
