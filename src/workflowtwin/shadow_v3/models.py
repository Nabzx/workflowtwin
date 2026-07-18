"""Strict-v3 protocol, detector, evaluation, lock, and audit contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from workflowtwin.source_contracts.observability import (
    ContractQualityMetrics,
    MissedPositiveAssessment,
    RecallCeiling,
)
from workflowtwin.source_contracts.states import EvidenceStability


class V3Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class V3DatasetRole(StrEnum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    HOLDOUT = "holdout"


class V3DatasetSpecification(V3Model):
    dataset_id: str
    role: V3DatasetRole
    seed: int
    case_count: int = Field(ge=1)
    operating_days: int = Field(ge=1)
    generation_run_id: str


class SourceQualityGates(V3Model):
    minimum_supported_form_rate: float = Field(ge=0, le=1)
    minimum_applicability_coverage: float = Field(ge=0, le=1)
    minimum_requirements_version_agreement: float = Field(ge=0, le=1)
    minimum_usable_input_coverage: float = Field(ge=0, le=1)
    maximum_stale_snapshot_rate: float = Field(ge=0, le=1)
    maximum_conflict_rate: float = Field(ge=0, le=1)


class V3Thresholds(V3Model):
    minimum_precision: float = Field(ge=0, le=1)
    minimum_recall: float = Field(ge=0, le=1)
    minimum_ceiling_relative_recall: float = Field(ge=0, le=1)
    maximum_false_positive_hours_per_100_cases: float = Field(ge=0)
    maximum_detector_positive_coverage: float = Field(gt=0, le=1)
    maximum_surfaced_coverage: float = Field(gt=0, le=1)
    maximum_p95_recommendation_latency_minutes: float = Field(gt=0)
    minimum_audit_completeness: float = Field(ge=0, le=1)
    minimum_policy_compliance: float = Field(ge=0, le=1)


class StrictV3Protocol(V3Model):
    protocol_id: str
    protocol_version: str
    detector_version: str
    detector_fingerprint: str
    policy_fingerprint: str
    source_contract_version: str
    source_contract_fingerprint: str
    requirements_contract_version: str
    requirements_contract_fingerprint: str
    capacity_profile: str
    capacity_fingerprint: str
    development_datasets: tuple[V3DatasetSpecification, ...]
    validation_dataset: V3DatasetSpecification
    holdout_dataset: V3DatasetSpecification
    thresholds: V3Thresholds
    source_quality_gates: SourceQualityGates
    supported_cohorts: tuple[str, ...]
    safety_gates: tuple[str, ...]
    audit_gates: tuple[str, ...]
    policy_gates: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    permitted_rule_changes: tuple[str, ...]
    prohibited_information: tuple[str, ...]
    rule_lock_version: str
    holdout_evaluation_count: int = 0


class V3Outcome(StrEnum):
    RECOMMEND = "recommend_administrative_review"
    OBSERVE_ONLY = "observe_only"
    PENDING = "confirmation_pending"
    NO_RECOMMENDATION = "no_recommendation"
    ABSTAIN = "abstain"
    RETRACT = "retract"


class V3DetectorResult(V3Model):
    evaluation_id: str
    case_id: UUID
    snapshot_id: str
    evaluated_at: datetime
    detector_version: str
    outcome: V3Outcome
    reason_codes: tuple[str, ...]
    relevant_fields: tuple[str, ...]
    evidence_stability: EvidenceStability
    confirmation_due_at: datetime | None
    recommendation_latency_minutes: float | None
    source_references: tuple[str, ...]
    accessed_fields: tuple[str, ...]
    recommendation_only: bool = True
    content_fingerprint: str


class V3AuditRecord(V3Model):
    audit_id: str
    run_id: str
    sequence_number: int
    occurred_at: datetime
    case_id: UUID | None
    action: str
    reason_codes: tuple[str, ...]
    input_references: tuple[str, ...]
    output_references: tuple[str, ...]
    previous_record_fingerprint: str | None
    content_fingerprint: str


class V3Run(V3Model):
    run_id: str
    detector_fingerprint: str
    source_contract_fingerprint: str
    requirements_contract_fingerprint: str
    results: tuple[V3DetectorResult, ...]
    audit_records: tuple[V3AuditRecord, ...]
    detector_positive_case_ids: tuple[UUID, ...]
    active_case_ids: tuple[UUID, ...]
    observe_only_case_ids: tuple[UUID, ...]
    retracted_case_ids: tuple[UUID, ...]
    run_fingerprint: str


class V3DetectorMetrics(V3Model):
    incoming_cases: int
    snapshots: int
    hidden_positives: int
    detector_positives: int
    active_recommendations: int
    surfaced_recommendations: int
    reviewed_recommendations: int
    abstentions: int
    contract_related_abstentions: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    unresolved_labels: int
    precision: float | None
    recall: float | None
    observable_recall_ceiling: float | None
    ceiling_relative_recall: float | None
    specificity: float | None
    false_positive_rate: float | None
    false_positive_review_hours: float
    detector_positive_coverage: float
    surfaced_coverage: float
    abstention_rate: float
    contract_abstention_rate: float
    retraction_rate: float
    mean_recommendation_latency_minutes: float | None
    p95_recommendation_latency_minutes: float | None
    reviewer_agreement: float | None
    usefulness_rate: float | None
    audit_completeness: float
    policy_compliance: float


class V3DatasetManifest(V3Model):
    dataset_id: str
    role: V3DatasetRole
    seed: int
    case_count: int
    operational_dataset_fingerprint: str
    v1_snapshot_fingerprint: str
    v2_snapshot_fingerprint: str
    requirements_contract_fingerprint: str
    hidden_label_fingerprint: str
    source_mix: dict[str, int]
    form_version_mix: dict[str, int]
    positive_prevalence: float
    generation_configuration: dict[str, Any]


class V3Evaluation(V3Model):
    manifest: V3DatasetManifest
    contract_quality: ContractQualityMetrics
    detector: V3DetectorMetrics
    capacity: dict[str, Any]
    ceilings: tuple[RecallCeiling, ...]
    missed_positives: tuple[MissedPositiveAssessment, ...]
    cohort_guardrails: tuple[dict[str, Any], ...]
    contradiction_counts: dict[str, int]
    source_contract_gates: dict[str, str]
    detector_gates: dict[str, str]
    capacity_gates: dict[str, str]
    safety_gates: dict[str, str]
    audit_gates: dict[str, str]
    policy_gates: dict[str, str]
    stop_condition_breaches: tuple[str, ...]
    promotion_assessment: str
    evaluation_fingerprint: str


class StrictV3Lock(V3Model):
    protocol_id: str
    detector_fingerprint: str
    policy_fingerprint: str
    source_contract_fingerprint: str
    requirements_contract_fingerprint: str
    capacity_fingerprint: str
    validation_evaluation_fingerprint: str
    validation_assessment: str
    locked_at: datetime
    lock_fingerprint: str


class V3HoldoutRegistry(V3Model):
    protocol_id: str
    dataset_id: str
    detector_fingerprint: str
    policy_fingerprint: str
    source_contract_fingerprint: str
    requirements_contract_fingerprint: str
    capacity_fingerprint: str
    lock_fingerprint: str
    evaluation_count: int
    evaluation_fingerprint: str | None
    status: str
