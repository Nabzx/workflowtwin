"""Typed recommendation, replay, review, audit, and evaluation contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from workflowtwin.domain.referrals.enums import ReferralSource, ServiceLine, SourceSystem
from workflowtwin.shadow.config import DetectorProfile


class ShadowModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldAvailability(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"


class IncomingReferralSnapshot(ShadowModel):
    """Fictional administrative intake facts available at one source watermark."""

    snapshot_id: str
    case_id: UUID
    available_at: datetime
    source_event_id: UUID | None
    source_system: SourceSystem
    referral_source: ReferralSource
    requested_service_line: ServiceLine
    submitting_organisation_id: str
    form_version: str
    source_record_version: int = Field(ge=1)
    referral_form: FieldAvailability
    supporting_document: FieldAvailability
    source_acknowledgement: FieldAvailability
    contact_route: FieldAvailability
    is_source_retry: bool = False
    is_synthetic: bool = True
    schema_version: int = 1


class ShadowLabelStatus(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNRESOLVED = "unresolved"
    NOT_EVALUABLE = "not_evaluable"
    AFTER_CUTOFF = "label_arrived_after_evaluation_cutoff"


class ShadowEvaluationLabel(ShadowModel):
    """Benchmark-only truth, deliberately incompatible with detector input."""

    label_id: str
    case_id: UUID
    valid_from: datetime
    valid_until: datetime | None = None
    status: ShadowLabelStatus
    evidence_codes: tuple[str, ...]
    is_synthetic: bool = True
    schema_version: int = 1


class AdministrativeFieldState(ShadowModel):
    referral_form: FieldAvailability
    supporting_document: FieldAvailability
    source_acknowledgement: FieldAvailability
    contact_route: FieldAvailability


class ShadowCaseState(ShadowModel):
    case_id: UUID
    state_version: int
    as_of: datetime
    referral_source: ReferralSource
    requested_service_line: ServiceLine
    source_system: SourceSystem
    form_version: str
    source_record_version: int
    fields: AdministrativeFieldState
    source_snapshot_ids: tuple[str, ...]
    stale_update_count: int = 0
    duplicate_update_count: int = 0
    warnings: tuple[str, ...] = ()


class DetectorOutcome(StrEnum):
    RECOMMEND = "recommend_review"
    NO_RECOMMENDATION = "no_recommendation"
    ABSTAIN = "abstain"
    BLOCKED = "blocked_by_policy"
    DUPLICATE_SUPPRESSED = "duplicate_suppressed"
    UNCHANGED = "recommendation_unchanged"
    REVISED = "recommendation_revised"
    RETRACTED = "recommendation_retracted"
    FAILURE = "detector_failure"


class ConfidenceClass(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class RecommendationStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    RETRACTED = "retracted"
    EXPIRED = "expired"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"
    SUPERSEDED = "superseded"
    CLOSED_WITHOUT_REVIEW = "closed_without_review"


class PolicyStatus(StrEnum):
    PERMITTED = "permitted"
    PERMITTED_WITH_WARNING = "permitted_with_warning"
    ABSTAIN_REQUIRED = "abstain_required"
    BLOCKED = "blocked"
    STOP_CONDITION_BREACH = "stop_condition_breach"


class PolicyEvaluation(ShadowModel):
    evaluation_id: str
    case_id: UUID
    evaluated_at: datetime
    status: PolicyStatus
    reason_codes: tuple[str, ...]
    allowed_fields: tuple[str, ...]
    prohibited_attempts: tuple[str, ...] = ()


class DetectorInput(ShadowModel):
    """Read-only as-of projection; contains no events, outcomes, reviews, or labels."""

    case_id: UUID
    as_of: datetime
    state_version: int
    referral_source: ReferralSource
    requested_service_line: ServiceLine
    source_system: SourceSystem
    form_version: str
    fields: AdministrativeFieldState
    source_snapshot_ids: tuple[str, ...]


class DetectorResult(ShadowModel):
    evaluation_id: str
    case_id: UUID
    evaluated_at: datetime
    detector_version: str
    profile: DetectorProfile
    outcome: DetectorOutcome
    reason_codes: tuple[str, ...]
    relevant_fields: tuple[str, ...]
    confidence: ConfidenceClass | None
    uncertainty_factors: tuple[str, ...]
    rationale: str
    accessed_fields: tuple[str, ...]


class Recommendation(ShadowModel):
    recommendation_id: str
    shadow_run_id: str
    case_id: UUID
    detector_version: str
    policy_version: str
    recommendation_at: datetime
    source_state_version: int
    lifecycle_version: int
    status: RecommendationStatus
    recommendation_type: str = "administrative_completeness_review"
    rationale: str
    reason_codes: tuple[str, ...]
    relevant_fields: tuple[str, ...]
    source_snapshot_ids: tuple[str, ...]
    confidence: ConfidenceClass
    uncertainty_factors: tuple[str, ...]
    expires_at: datetime
    reviewer_role_required: str
    prohibited_follow_on_actions: tuple[str, ...]
    policy_evaluation_id: str
    audit_record_id: str
    warnings: tuple[str, ...] = ()


class ReviewDecisionType(StrEnum):
    AGREE = "agree"
    DISAGREE = "disagree"
    UNCERTAIN = "uncertain"
    ALREADY_RESOLVED = "already_resolved"
    DUPLICATE = "duplicate"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    POLICY_CONCERN = "policy_concern"
    EXPIRED_BEFORE_REVIEW = "expired_before_review"
    NOT_REVIEWED = "not_reviewed"


class ReviewDecision(ShadowModel):
    review_id: str
    recommendation_id: str
    recommendation_lifecycle_version: int
    case_id: UUID
    reviewer_id: str
    reviewer_role: str
    decided_at: datetime
    decision: ReviewDecisionType
    reason_codes: tuple[str, ...]
    recommendation_useful: bool | None
    completeness_review_required: bool | None
    arrived_in_time: bool | None
    override_or_correction: bool = False
    comment: str | None = Field(default=None, max_length=240)
    review_duration_minutes: float = Field(ge=0)
    decision_source: str
    is_synthetic: bool = True
    schema_version: int = 1

    @field_validator("comment")
    @classmethod
    def reject_sensitive_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalised = value.lower().replace("-", "_").replace(" ", "_")
        forbidden = {
            "patient_name",
            "nhs_number",
            "diagnosis",
            "symptoms",
            "medical_history",
            "treatment",
            "email_address",
            "phone_number",
        }
        if any(term in normalised for term in forbidden):
            raise ValueError("review comments cannot contain clinical or identifying information")
        return value


class AuditActor(StrEnum):
    SOURCE = "source"
    SYSTEM = "shadow_system"
    DETECTOR = "detector"
    POLICY = "policy"
    REVIEWER = "reviewer"
    EVALUATOR = "evaluator"


class AuditRecord(ShadowModel):
    audit_id: str
    shadow_run_id: str
    sequence_number: int
    occurred_at: datetime
    case_id: UUID | None
    recommendation_id: str | None
    actor: AuditActor
    action: str
    reason_codes: tuple[str, ...]
    input_references: tuple[str, ...]
    output_references: tuple[str, ...]
    detector_version: str
    policy_version: str
    content_fingerprint: str
    previous_record_fingerprint: str | None


class ReplayCheckpoint(ShadowModel):
    shadow_run_id: str
    last_source_position: int
    source_fingerprint: str
    detector_version: str
    policy_version: str
    case_state_fingerprints: dict[str, str]
    active_recommendation_ids: tuple[str, ...]
    audit_root_fingerprint: str | None
    case_states: tuple[ShadowCaseState, ...] = ()
    recommendations: tuple[Recommendation, ...] = ()
    policy_evaluations: tuple[PolicyEvaluation, ...] = ()
    detector_results: tuple[DetectorResult, ...] = ()
    audit_records: tuple[AuditRecord, ...] = ()
    checkpoint_fingerprint: str


class ShadowRunManifest(ShadowModel):
    shadow_mode_version: str
    shadow_run_id: str
    detector_profile: DetectorProfile
    detector_version: str
    policy_version: str
    source_dataset_fingerprint: str
    intake_snapshot_fingerprint: str
    opportunity_identifier: str
    opportunity_analysis_fingerprint: str
    simulation_analysis_fingerprint: str
    source_period_start: datetime | None
    source_period_end: datetime | None
    replay_ordering: str
    source_items_processed: int
    cases_observed: int
    eligible_cases: int
    detector_evaluations: int
    recommendations: int
    abstentions: int
    revisions: int
    retractions: int
    expiries: int
    duplicate_suppressions: int
    reviews: int
    policy_blocks: int
    stop_condition_breaches: int
    audit_record_count: int
    audit_root_fingerprint: str | None
    run_status: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    fictional_data_declaration: str
    recommendation_only_declaration: str
    manifest_fingerprint: str


class MetricValue(ShadowModel):
    value: float | int | None
    numerator: int | None = None
    denominator: int | None = None
    unit: str
    status: str = "available"


class DetectorEvaluation(ShadowModel):
    incoming_cases: int
    evaluated_cases: int
    recommendations: int
    abstentions: int
    reviewed_recommendations: int
    evaluable_recommendations: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    unresolved_labels: int
    recommendation_coverage: MetricValue
    abstention_rate: MetricValue
    precision: MetricValue
    recall: MetricValue
    specificity: MetricValue
    false_positive_rate: MetricValue
    false_negative_rate: MetricValue
    negative_predictive_value: MetricValue
    f1_score: MetricValue
    evaluation_coverage: MetricValue


class LatencySummary(ShadowModel):
    count: int
    unavailable_count: int
    mean_minutes: float | None
    median_minutes: float | None
    p90_minutes: float | None
    p95_minutes: float | None
    maximum_minutes: float | None
    slo_compliance_rate: float | None


class BurdenReport(ShadowModel):
    all_review_hours: float
    false_positive_review_hours: float
    useful_review_hours: float
    unresolved_review_hours: float
    false_positive_per_100_cases: float
    false_positive_per_100_recommendations: float
    fictional_false_positive_cost_gbp: float
    revision_count: int
    retraction_count: int
    expiry_count: int


class ReviewerMetrics(ShadowModel):
    review_count: int
    completion_rate: float | None
    agreement_rate: float | None
    rejection_rate: float | None
    uncertainty_rate: float | None
    already_resolved_rate: float | None
    policy_concern_rate: float | None
    override_rate: float | None
    median_review_duration_minutes: float | None
    timeout_rate: float | None
    usefulness_counts: dict[str, int]


class AuditQuality(ShadowModel):
    total_records: int
    complete_records: int
    missing_required_references: int
    invalid_action_sequences: int
    broken_chain_links: int
    missing_policy_evaluations: int
    orphan_recommendations: int
    orphan_reviews: int
    audit_completeness_rate: float
    chain_valid: bool


class PolicyCompliance(ShadowModel):
    detector_evaluations: int
    permitted_evaluations: int
    blocked_evaluations: int
    abstentions_required: int
    active_recommendations_with_approval: int
    recommendations_missing_approval: int
    prohibited_input_attempts: int
    clinical_field_access_attempts: int
    workflow_mutation_attempts: int
    external_communication_attempts: int
    total_policy_violations: int
    compliance_rate: float


class GateStatus(StrEnum):
    PASSED = "gate_passed"
    FAILED = "gate_failed"
    INSUFFICIENT = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"


class PromotionGate(ShadowModel):
    gate_id: str
    category: str
    status: GateStatus
    observed_value: float | int | bool | None
    threshold: float | int | bool | None
    mandatory: bool
    explanation: str


class StopConditionResult(ShadowModel):
    condition_id: str
    metric: str
    breached: bool
    severity: str
    action: str
    observed_value: float | int | bool | None
    threshold: float | int | bool
    minimum_sample_size: int
    explanation: str


class PromotionAssessment(ShadowModel):
    result: str
    mandatory_gates_passed: bool
    stop_condition_breached: bool
    gate_counts: dict[str, int]
    explanation: str
    assessment_fingerprint: str


class ShadowEvaluation(ShadowModel):
    source_fingerprints: dict[str, str]
    configuration: dict[str, JsonValue]
    run_manifest: ShadowRunManifest
    detector: DetectorEvaluation
    source_to_recommendation_latency: LatencySummary
    case_arrival_to_recommendation_latency: LatencySummary
    recommendation_to_review_latency: LatencySummary
    resolution_before_review_latency: LatencySummary
    detector_runtime_seconds: float
    reviewer: ReviewerMetrics
    burden: BurdenReport
    audit: AuditQuality
    policy: PolicyCompliance
    cohort_breakdowns: tuple[dict[str, Any], ...]
    time_windows: tuple[dict[str, Any], ...]
    profile_comparison: tuple[dict[str, Any], ...]
    stop_conditions: tuple[StopConditionResult, ...]
    promotion_gates: tuple[PromotionGate, ...]
    promotion_assessment: PromotionAssessment
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    evaluation_fingerprint: str


class ShadowRun(ShadowModel):
    config: dict[str, JsonValue]
    manifest: ShadowRunManifest
    case_states: tuple[ShadowCaseState, ...]
    policy_evaluations: tuple[PolicyEvaluation, ...]
    detector_results: tuple[DetectorResult, ...]
    recommendations: tuple[Recommendation, ...]
    audit_records: tuple[AuditRecord, ...]
    checkpoint: ReplayCheckpoint
