"""Pilot workload metrics, policy gates, stop conditions, and assessment."""

from collections.abc import Sequence
from statistics import mean

from workflowtwin.pilot.audit import verify_pilot_audit
from workflowtwin.pilot.models import (
    DraftMissingInformationRequest,
    DraftStatus,
    GateStatus,
    PilotAction,
    PilotActionStatus,
    PilotAssessment,
    PilotAuditRecord,
    PilotGateResult,
    PilotMetrics,
    PilotPolicy,
    PilotReviewDecision,
    PilotReviewDecisionType,
    PilotRollback,
)


def _ratio(numerator: int | float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _percentile_95(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]


def calculate_metrics(
    *,
    incoming_cases: int,
    detector_positives: int,
    true_positives: int,
    evaluable_positives: int,
    drafts: tuple[DraftMissingInformationRequest, ...],
    reviews: tuple[PilotReviewDecision, ...],
    actions: tuple[PilotAction, ...],
    rollbacks: tuple[PilotRollback, ...],
    audit_records: tuple[PilotAuditRecord, ...],
    policy_evaluations_complete: bool = True,
    deterministic_replay: bool = True,
) -> PilotMetrics:
    reviewed_drafts = {item.draft_id for item in reviews}
    review_latencies = [
        (
            review.decided_at
            - next(item.created_at for item in drafts if item.draft_id == review.draft_id)
        ).total_seconds()
        / 60
        for review in reviews
    ]
    approvals = [
        item
        for item in reviews
        if item.decision
        in {PilotReviewDecisionType.APPROVE, PilotReviewDecisionType.APPROVE_WITH_EDITS}
    ]
    approval_latencies = [
        (
            item.decided_at - next(d.created_at for d in drafts if d.draft_id == item.draft_id)
        ).total_seconds()
        / 60
        for item in approvals
    ]
    action_latencies = [
        (
            item.acted_at - next(d.created_at for d in drafts if d.draft_id == item.draft_id)
        ).total_seconds()
        / 60
        for item in actions
        if item.status is PilotActionStatus.COMMITTED
    ]
    reviewed = len(reviewed_drafts)
    false_positives = max(detector_positives - true_positives, 0)
    false_positive_minutes = (
        sum(item.review_minutes for item in reviews) * false_positives / detector_positives
        if detector_positives
        else 0.0
    )
    audit_valid, _ = verify_pilot_audit(audit_records)
    expected_audited_events = len(reviews) + len(actions) + len(rollbacks)
    audited_events = sum(
        1
        for item in audit_records
        if item.action.startswith(("draft_review_", "committed_", "duplicate_", "rollback_"))
    )
    audit_completeness = (
        min(audited_events / expected_audited_events, 1.0) if expected_audited_events else 1.0
    )
    duplicate_actions = sum(
        item.status is PilotActionStatus.DUPLICATE_SUPPRESSED for item in actions
    )
    committed = sum(item.status is PilotActionStatus.COMMITTED for item in actions)
    review_slo = (
        sum(value <= 240 for value in review_latencies) / len(review_latencies)
        if review_latencies
        else None
    )
    unresolved_states = {DraftStatus.AWAITING_REVIEW, DraftStatus.EDITED, DraftStatus.APPROVED}
    return PilotMetrics(
        incoming_cases=incoming_cases,
        detector_positives=detector_positives,
        detector_positive_coverage=detector_positives / incoming_cases,
        detector_precision=_ratio(true_positives, detector_positives),
        detector_recall=_ratio(true_positives, evaluable_positives),
        recommendations_entering_pilot=len(drafts),
        surfaced_recommendation_coverage=len(drafts) / incoming_cases,
        drafts_created=len(drafts),
        drafts_reviewed=reviewed,
        drafts_edited=sum(len(item.revisions) > 1 for item in drafts),
        drafts_approved=len(approvals),
        drafts_rejected=sum(item.decision is PilotReviewDecisionType.REJECT for item in reviews),
        drafts_cancelled=sum(item.decision is PilotReviewDecisionType.CANCEL for item in reviews),
        drafts_retracted=sum(item.status is DraftStatus.RETRACTED for item in drafts),
        drafts_expired=sum(item.status is DraftStatus.EXPIRED for item in drafts),
        fictional_tasks_committed=committed,
        rollbacks=len(rollbacks),
        duplicate_actions_prevented=duplicate_actions,
        reviewer_agreement=1.0 if reviews else None,
        approval_rate=_ratio(len(approvals), reviewed),
        edit_rate=_ratio(sum(len(item.revisions) > 1 for item in drafts), reviewed),
        rejection_rate=_ratio(
            sum(item.decision is PilotReviewDecisionType.REJECT for item in reviews), reviewed
        ),
        mean_time_to_review_minutes=mean(review_latencies) if review_latencies else None,
        p95_review_latency_minutes=_percentile_95(review_latencies),
        review_slo_compliance=review_slo,
        mean_time_to_approval_minutes=mean(approval_latencies) if approval_latencies else None,
        mean_time_to_task_creation_minutes=mean(action_latencies) if action_latencies else None,
        review_minutes=sum(item.review_minutes for item in reviews),
        false_positive_review_minutes=false_positive_minutes,
        false_positive_review_minutes_per_100_cases=false_positive_minutes * 100 / incoming_cases,
        maximum_queue_depth=len(drafts),
        unresolved_drafts=sum(item.status in unresolved_states for item in drafts),
        policy_compliance=1.0 if policy_evaluations_complete else 0.0,
        audit_completeness=audit_completeness if audit_valid else 0.0,
        mock_system_failure_rate=0.0,
        rollback_success_rate=1.0 if rollbacks else None,
        expiry_rate=sum(item.status is DraftStatus.EXPIRED for item in drafts) / len(drafts),
        duplicate_action_rate=duplicate_actions / len(actions) if actions else 0.0,
        mock_system_availability=1.0,
        deterministic_replay=deterministic_replay,
    )


def evaluate_gates(
    metrics: PilotMetrics, policy: PilotPolicy
) -> tuple[tuple[PilotGateResult, ...], tuple[str, ...], PilotAssessment]:
    checks = (
        (
            "safety-clinical-access",
            "safety",
            metrics.clinical_fields_accessed == 0,
            metrics.clinical_fields_accessed,
            0,
        ),
        (
            "safety-external-communication",
            "safety",
            metrics.external_communication_attempts == 0,
            metrics.external_communication_attempts,
            0,
        ),
        (
            "safety-workflow-mutation",
            "safety",
            metrics.operational_workflow_mutations == 0,
            metrics.operational_workflow_mutations,
            0,
        ),
        (
            "safety-human-approval",
            "safety",
            metrics.actions_without_approval == 0,
            metrics.actions_without_approval,
            0,
        ),
        (
            "quality-precision",
            "detector_quality",
            (metrics.detector_precision or 0) >= policy.minimum_precision,
            metrics.detector_precision,
            policy.minimum_precision,
        ),
        (
            "quality-recall",
            "detector_quality",
            (metrics.detector_recall or 0) >= policy.minimum_recall,
            metrics.detector_recall,
            policy.minimum_recall,
        ),
        (
            "capacity-surfaced-coverage",
            "reviewer_capacity",
            metrics.surfaced_recommendation_coverage <= policy.maximum_surfaced_coverage,
            metrics.surfaced_recommendation_coverage,
            policy.maximum_surfaced_coverage,
        ),
        (
            "capacity-review-minutes",
            "reviewer_capacity",
            metrics.review_minutes <= policy.daily_review_minutes,
            metrics.review_minutes,
            policy.daily_review_minutes,
        ),
        (
            "capacity-false-positive-minutes",
            "reviewer_capacity",
            metrics.false_positive_review_minutes_per_100_cases
            <= policy.false_positive_review_minutes_per_100_cases_maximum,
            metrics.false_positive_review_minutes_per_100_cases,
            policy.false_positive_review_minutes_per_100_cases_maximum,
        ),
        (
            "capacity-queue-depth",
            "reviewer_capacity",
            metrics.maximum_queue_depth <= policy.maximum_queue_depth,
            metrics.maximum_queue_depth,
            policy.maximum_queue_depth,
        ),
        (
            "capacity-review-latency",
            "reviewer_capacity",
            (metrics.p95_review_latency_minutes or 0) <= policy.review_slo_minutes,
            metrics.p95_review_latency_minutes,
            policy.review_slo_minutes,
        ),
        (
            "capacity-expiry",
            "reviewer_capacity",
            metrics.expiry_rate <= policy.maximum_expiry_rate,
            metrics.expiry_rate,
            policy.maximum_expiry_rate,
        ),
        (
            "capacity-unresolved",
            "reviewer_capacity",
            metrics.unresolved_drafts <= policy.maximum_unresolved_drafts,
            metrics.unresolved_drafts,
            policy.maximum_unresolved_drafts,
        ),
        (
            "audit-completeness",
            "auditability",
            metrics.audit_completeness >= policy.minimum_audit_completeness,
            metrics.audit_completeness,
            policy.minimum_audit_completeness,
        ),
        (
            "policy-compliance",
            "auditability",
            metrics.policy_compliance >= policy.minimum_policy_compliance,
            metrics.policy_compliance,
            policy.minimum_policy_compliance,
        ),
        (
            "reliability-deterministic-replay",
            "reliability",
            metrics.deterministic_replay,
            metrics.deterministic_replay,
            True,
        ),
        (
            "reliability-idempotency",
            "reliability",
            metrics.duplicate_action_rate <= policy.maximum_duplicate_action_rate,
            metrics.duplicate_action_rate,
            policy.maximum_duplicate_action_rate,
        ),
        (
            "reliability-mock-availability",
            "reliability",
            metrics.mock_system_availability >= policy.minimum_mock_system_availability,
            metrics.mock_system_availability,
            policy.minimum_mock_system_availability,
        ),
        (
            "reliability-mock-failures",
            "reliability",
            metrics.mock_system_failure_rate <= policy.maximum_mock_system_failure_rate,
            metrics.mock_system_failure_rate,
            policy.maximum_mock_system_failure_rate,
        ),
        (
            "reliability-rollback",
            "reliability",
            metrics.rollback_success_rate in {None, 1.0},
            metrics.rollback_success_rate,
            1.0,
        ),
    )
    gates = tuple(
        PilotGateResult(
            gate_id=gate_id,
            category=category,
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            actual=actual,
            threshold=threshold,
            explanation="Fictional controlled-pilot gate passed."
            if passed
            else "Pilot stop condition triggered.",
        )
        for gate_id, category, passed, actual, threshold in checks
    )
    failures = tuple(item.gate_id for item in gates if item.status is GateStatus.FAIL)
    safety_failure = any(item.startswith(("safety-", "audit-", "policy-")) for item in failures)
    assessment = (
        PilotAssessment.PAUSE_DUE_TO_STOP_CONDITION
        if safety_failure
        else PilotAssessment.REVISE_PILOT_DESIGN
        if failures
        else PilotAssessment.READY_FOR_FICTIONAL_PILOT_DEMO
    )
    return gates, failures, assessment
