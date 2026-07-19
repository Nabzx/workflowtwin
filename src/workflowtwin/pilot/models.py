"""Typed contracts for the reversible, human-approved fictional pilot."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

FICTIONAL_PILOT_DECLARATION = (
    "Fictional Northstar administrative pilot; no message is sent and no referral is changed."
)


class PilotModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DraftStatus(StrEnum):
    CREATED = "draft_created"
    AWAITING_REVIEW = "draft_awaiting_review"
    EDITED = "draft_edited"
    APPROVED = "draft_approved"
    REJECTED = "draft_rejected"
    CANCELLED = "draft_cancelled"
    EXPIRED = "draft_expired"
    RETRACTED = "draft_retracted"
    COMMITTED = "draft_committed_to_fictional_task_queue"
    ROLLED_BACK = "draft_rolled_back"
    CLOSED = "draft_closed"


class PilotReviewDecisionType(StrEnum):
    APPROVE = "approve"
    APPROVE_WITH_EDITS = "approve_with_edits"
    REJECT = "reject"
    CANCEL = "cancel"
    MARK_UNNECESSARY = "mark_unnecessary"
    REQUEST_MORE_CONTEXT = "request_more_context"


class PilotActionStatus(StrEnum):
    COMMITTED = "committed_to_mock_system"
    DUPLICATE_SUPPRESSED = "duplicate_action_suppressed"
    ROLLED_BACK = "rolled_back"
    FAILED = "mock_action_failed"


class MockTaskStatus(StrEnum):
    READY_FOR_MANUAL_SENDING = "ready_for_manual_sending"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class GateStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


class PilotAssessment(StrEnum):
    READY_FOR_FICTIONAL_PILOT_DEMO = "ready_for_fictional_pilot_demo"
    CONTINUE_SHADOW_ONLY = "continue_shadow_only"
    REVISE_PILOT_DESIGN = "revise_pilot_design"
    PAUSE_DUE_TO_STOP_CONDITION = "pause_due_to_stop_condition"
    DO_NOT_PROCEED = "do_not_proceed"


class PilotPolicy(PilotModel):
    policy_version: str
    supported_detector: str
    action_type: str
    permitted_reviewer_roles: tuple[str, ...]
    minimum_precision: float = Field(ge=0, le=1)
    minimum_recall: float = Field(ge=0, le=1)
    maximum_surfaced_coverage: float = Field(gt=0, le=1)
    daily_review_minutes: float = Field(gt=0)
    review_minutes_per_draft: float = Field(gt=0)
    false_positive_review_minutes_per_100_cases_maximum: float = Field(ge=0)
    maximum_queue_depth: int = Field(ge=1)
    review_slo_minutes: float = Field(gt=0)
    maximum_expiry_rate: float = Field(ge=0, le=1)
    maximum_unresolved_drafts: int = Field(ge=0)
    minimum_policy_compliance: float = Field(ge=0, le=1)
    minimum_audit_completeness: float = Field(ge=0, le=1)
    maximum_duplicate_action_rate: float = Field(ge=0, le=1)
    minimum_mock_system_availability: float = Field(ge=0, le=1)
    maximum_mock_system_failure_rate: float = Field(ge=0, le=1)
    maximum_rollback_failure_rate: float = Field(ge=0, le=1)
    rollback_required: bool


class PilotRecommendation(PilotModel):
    recommendation_id: str
    detector_evaluation_id: str
    case_id: UUID
    snapshot_id: str
    detected_at: datetime
    missing_field_ids: tuple[str, ...]
    source_references: tuple[str, ...]
    requirement_references: tuple[str, ...]
    detector_product_name: str
    supported_detector_fingerprint: str
    original_detector_fingerprint: str
    current: bool = True
    unresolved_source_conflict: bool = False
    recommendation_only: bool = True


class DraftItem(PilotModel):
    field_id: str
    display_name: str
    requirement_id: str


class DraftRevision(PilotModel):
    revision_id: str
    previous_revision_id: str | None
    editor_role: str
    revised_at: datetime
    change_reason: str
    changed_fields: tuple[str, ...]
    heading: str
    body: str
    items: tuple[DraftItem, ...]
    audit_reference: str


class DraftMissingInformationRequest(PilotModel):
    draft_id: str
    recommendation_id: str
    case_id: UUID
    administrative_recipient_role: str
    form_version: str
    source_snapshot_references: tuple[str, ...]
    requirements_contract_references: tuple[str, ...]
    created_at: datetime
    expires_at: datetime
    status: DraftStatus
    current_revision_id: str
    revisions: tuple[DraftRevision, ...]
    human_review_required: bool = True
    no_message_sent: bool = True
    fictional_declaration: str = FICTIONAL_PILOT_DECLARATION

    @model_validator(mode="after")
    def preserve_safety_boundary(self) -> "DraftMissingInformationRequest":
        if not self.human_review_required or not self.no_message_sent:
            raise ValueError(
                "pilot drafts require human review and cannot represent a sent message"
            )
        if self.current_revision_id not in {item.revision_id for item in self.revisions}:
            raise ValueError("current draft revision is missing")
        return self


class PilotReviewDecision(PilotModel):
    review_id: str
    draft_id: str
    recommendation_id: str
    revision_id: str
    reviewer_role: str
    decision: PilotReviewDecisionType
    decided_at: datetime
    structured_reason: str
    policy_evaluation_id: str
    review_minutes: float = Field(ge=0)


class PilotAction(PilotModel):
    action_id: str
    idempotency_key: str
    recommendation_id: str
    draft_id: str
    revision_id: str
    review_id: str
    action_type: str
    status: PilotActionStatus
    mock_task_id: str | None
    acted_at: datetime
    actor_role: str
    no_external_communication: bool = True
    operational_events_mutated: bool = False


class PilotRollback(PilotModel):
    rollback_id: str
    action_id: str
    mock_task_id: str
    actor_role: str
    reason: str
    rolled_back_at: datetime
    restored_status: MockTaskStatus
    duplicate_request: bool = False


class MockTaskHistoryItem(PilotModel):
    history_id: str
    occurred_at: datetime
    actor_role: str
    action: str
    reason: str
    previous_status: MockTaskStatus | None
    new_status: MockTaskStatus


class MockReferralSystemRecord(PilotModel):
    task_id: str
    idempotency_key: str
    case_id: UUID
    draft_id: str
    revision_id: str
    status: MockTaskStatus
    heading: str
    body: str
    item_ids: tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    history: tuple[MockTaskHistoryItem, ...]
    message_sent: bool = False


class PilotAuditRecord(PilotModel):
    audit_id: str
    sequence_number: int
    occurred_at: datetime
    actor_role: str
    action: str
    object_id: str
    input_references: tuple[str, ...]
    output_references: tuple[str, ...]
    reason_codes: tuple[str, ...]
    previous_record_fingerprint: str | None
    content_fingerprint: str


class PilotMetrics(PilotModel):
    incoming_cases: int
    detector_positives: int
    detector_positive_coverage: float
    recommendations_entering_pilot: int
    surfaced_recommendation_coverage: float
    drafts_created: int
    drafts_reviewed: int
    drafts_edited: int
    drafts_approved: int
    drafts_rejected: int
    drafts_cancelled: int
    drafts_retracted: int
    drafts_expired: int
    fictional_tasks_committed: int
    rollbacks: int
    duplicate_actions_prevented: int
    reviewer_agreement: float | None
    approval_rate: float | None
    edit_rate: float | None
    rejection_rate: float | None
    mean_time_to_review_minutes: float | None
    p95_review_latency_minutes: float | None
    mean_time_to_approval_minutes: float | None
    mean_time_to_task_creation_minutes: float | None
    review_minutes: float
    false_positive_review_minutes: float
    maximum_queue_depth: int
    unresolved_drafts: int
    policy_compliance: float
    audit_completeness: float
    mock_system_failure_rate: float
    rollback_success_rate: float | None
    expiry_rate: float
    duplicate_action_rate: float


class PilotGateResult(PilotModel):
    gate_id: str
    category: str
    status: GateStatus
    actual: float | int | bool | None
    threshold: float | int | bool | None
    explanation: str


class PilotRun(PilotModel):
    run_id: str
    created_at: datetime
    policy: PilotPolicy
    policy_fingerprint: str
    supported_detector_metadata: dict[str, str | bool]
    input_fingerprints: dict[str, str]
    recommendations: tuple[PilotRecommendation, ...]
    drafts: tuple[DraftMissingInformationRequest, ...]
    reviews: tuple[PilotReviewDecision, ...]
    actions: tuple[PilotAction, ...]
    rollbacks: tuple[PilotRollback, ...]
    mock_records: tuple[MockReferralSystemRecord, ...]
    metrics: PilotMetrics
    gates: tuple[PilotGateResult, ...]
    stop_conditions: tuple[str, ...]
    assessment: PilotAssessment
    audit_records: tuple[PilotAuditRecord, ...]
    audit_root_fingerprint: str | None
    run_fingerprint: str
    fictional_declaration: str = FICTIONAL_PILOT_DECLARATION
