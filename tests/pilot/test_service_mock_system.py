"""Human approval, idempotency, rollback, and source-immutability tests."""

from datetime import timedelta

import pytest

from workflowtwin.core.fingerprint import fingerprint
from workflowtwin.pilot.audit import verify_pilot_audit
from workflowtwin.pilot.drafts import create_draft, revise_draft
from workflowtwin.pilot.mock_system import (
    InMemoryMockReferralSystem,
    MockTaskNotFoundError,
)
from workflowtwin.pilot.models import (
    DraftStatus,
    MockTaskStatus,
    PilotActionStatus,
    PilotRecommendation,
    PilotReviewDecisionType,
)
from workflowtwin.pilot.policy import load_pilot_policy
from workflowtwin.pilot.service import PilotNotFoundError, PilotService
from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2


def _service(
    recommendation: PilotRecommendation,
    snapshot: IncomingReferralSnapshotV2,
) -> tuple[PilotService, str]:
    draft = create_draft(recommendation=recommendation, snapshot=snapshot)
    service = PilotService(
        policy=load_pilot_policy(),
        recommendations=(recommendation,),
        drafts=(draft,),
    )
    return service, draft.draft_id


def test_action_requires_matching_human_approval(
    pilot_recommendation: PilotRecommendation,
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    service, draft_id = _service(pilot_recommendation, v2_source[0][0])
    with pytest.raises(PilotNotFoundError, match="review"):
        service.commit_approved(
            draft_id,
            review_id="missing-review",
            acted_at=pilot_recommendation.detected_at + timedelta(minutes=5),
        )


def test_approval_commit_and_replay_are_local_and_idempotent(
    pilot_recommendation: PilotRecommendation,
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    snapshots = v2_source[0]
    source_before = fingerprint(snapshots)
    service, draft_id = _service(pilot_recommendation, snapshots[0])
    draft = service.draft(draft_id)
    review = service.review(
        draft_id,
        revision_id=draft.current_revision_id,
        reviewer_role="fictional_admin_reviewer",
        decision=PilotReviewDecisionType.APPROVE,
        decided_at=draft.created_at + timedelta(minutes=4),
        structured_reason="administrative evidence verified",
        review_minutes=4,
    )
    first = service.commit_approved(
        draft_id,
        review_id=review.review_id,
        acted_at=draft.created_at + timedelta(minutes=5),
    )
    repeated = service.commit_approved(
        draft_id,
        review_id=review.review_id,
        acted_at=draft.created_at + timedelta(minutes=6),
    )
    assert first.status is PilotActionStatus.COMMITTED
    assert repeated.status is PilotActionStatus.DUPLICATE_SUPPRESSED
    assert first.idempotency_key == repeated.idempotency_key
    assert first.mock_task_id == repeated.mock_task_id
    assert len(service.mock_system.list_tasks()) == 1
    task = service.mock_system.read_task(first.mock_task_id or "")
    assert task.message_sent is False
    assert task.status is MockTaskStatus.READY_FOR_MANUAL_SENDING
    assert fingerprint(snapshots) == source_before
    assert verify_pilot_audit(service.audit_records)[0] is True


def test_edit_reject_cancel_and_expired_review_lifecycle(
    pilot_recommendation: PilotRecommendation,
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    service, draft_id = _service(pilot_recommendation, v2_source[0][0])
    draft = service.draft(draft_id)
    edited = service.edit_draft(
        draft_id,
        editor_role="fictional_admin_reviewer",
        revised_at=draft.created_at + timedelta(minutes=1),
        change_reason="clearer wording",
        heading="Administrative evidence check",
    )
    review = service.review(
        draft_id,
        revision_id=edited.current_revision_id,
        reviewer_role="fictional_admin_reviewer",
        decision=PilotReviewDecisionType.REJECT,
        decided_at=draft.created_at + timedelta(minutes=2),
        structured_reason="source evidence already complete",
        review_minutes=2,
    )
    assert review.decision is PilotReviewDecisionType.REJECT
    assert service.draft(draft_id).status is DraftStatus.REJECTED
    with pytest.raises(ValueError, match="approved"):
        service.commit_approved(
            draft_id,
            review_id=review.review_id,
            acted_at=draft.created_at + timedelta(minutes=3),
        )

    other, other_id = _service(pilot_recommendation, v2_source[0][0])
    other_draft = other.draft(other_id)
    with pytest.raises(ValueError, match="expired"):
        other.review(
            other_id,
            revision_id=other_draft.current_revision_id,
            reviewer_role="fictional_admin_reviewer",
            decision=PilotReviewDecisionType.CANCEL,
            decided_at=other_draft.expires_at,
            structured_reason="review window closed",
            review_minutes=1,
        )


def test_rollback_is_idempotent_and_works_after_mock_task_cancellation(
    pilot_recommendation: PilotRecommendation,
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    service, draft_id = _service(pilot_recommendation, v2_source[0][0])
    draft = service.draft(draft_id)
    review = service.review(
        draft_id,
        revision_id=draft.current_revision_id,
        reviewer_role="fictional_pilot_supervisor",
        decision=PilotReviewDecisionType.APPROVE,
        decided_at=draft.created_at + timedelta(minutes=1),
        structured_reason="fictional pilot approval",
        review_minutes=1,
    )
    action = service.commit_approved(
        draft_id,
        review_id=review.review_id,
        acted_at=draft.created_at + timedelta(minutes=2),
    )
    task_id = action.mock_task_id or ""
    service.mock_system.cancel_task(
        task_id,
        actor_role="fictional_pilot_supervisor",
        reason="superseding evidence",
        occurred_at=draft.created_at + timedelta(minutes=3),
    )
    first = service.rollback(
        action.action_id,
        actor_role="fictional_pilot_supervisor",
        reason="restore pre-pilot state",
        rolled_back_at=draft.created_at + timedelta(minutes=4),
    )
    repeated = service.rollback(
        action.action_id,
        actor_role="fictional_pilot_supervisor",
        reason="replayed rollback",
        rolled_back_at=draft.created_at + timedelta(minutes=5),
    )
    assert first.duplicate_request is False
    assert repeated.duplicate_request is True
    assert service.mock_system.read_task(task_id).status is MockTaskStatus.ROLLED_BACK
    assert len(service.rollbacks) == 1
    assert len(service.mock_system.list_task_history(task_id)) == 3
    assert verify_pilot_audit(service.audit_records)[0] is True
    with pytest.raises(PilotNotFoundError, match="action"):
        service.rollback(
            "unknown-action",
            actor_role="fictional_pilot_supervisor",
            reason="invalid",
            rolled_back_at=draft.created_at + timedelta(minutes=6),
        )


def test_mock_system_rejects_unknown_tasks() -> None:
    system = InMemoryMockReferralSystem()
    with pytest.raises(MockTaskNotFoundError, match="unknown"):
        system.read_task("missing")


def test_expiry_retraction_and_mock_update_lifecycle(
    pilot_recommendation: PilotRecommendation,
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    snapshot = v2_source[0][0]
    service, draft_id = _service(pilot_recommendation, snapshot)
    draft = service.draft(draft_id)
    assert service.expire_due(as_of=draft.expires_at - timedelta(seconds=1)) == ()
    assert service.expire_due(as_of=draft.expires_at) == (draft_id,)
    assert service.draft(draft_id).status is DraftStatus.EXPIRED

    other, other_id = _service(pilot_recommendation, snapshot)
    retracted = other.retract(
        other_id,
        retracted_at=draft.created_at + timedelta(minutes=3),
        actor_role="workflowtwin_system",
        reason="superseding source evidence resolved concern",
    )
    assert retracted.status is DraftStatus.RETRACTED
    assert other.recommendation(retracted.recommendation_id).current is False
    with pytest.raises(ValueError, match="current state"):
        other.retract(
            other_id,
            retracted_at=draft.created_at + timedelta(minutes=4),
            actor_role="workflowtwin_system",
            reason="duplicate",
        )

    system = InMemoryMockReferralSystem()
    record, _ = system.create_task(
        draft=draft,
        idempotency_key="mock-update-key",
        actor_role="fictional_admin_reviewer",
        occurred_at=draft.created_at + timedelta(minutes=1),
    )
    edited = revise_draft(
        draft,
        editor_role="fictional_admin_reviewer",
        revised_at=draft.created_at + timedelta(minutes=2),
        change_reason="approved wording",
        heading="Updated administrative heading",
    )
    updated = system.update_approved_draft(
        record.task_id,
        draft=edited,
        actor_role="fictional_admin_reviewer",
        reason="approved current revision",
        occurred_at=draft.created_at + timedelta(minutes=3),
    )
    assert updated.revision_id == edited.current_revision_id
    system.cancel_task(
        record.task_id,
        actor_role="fictional_admin_reviewer",
        reason="temporary cancellation",
        occurred_at=draft.created_at + timedelta(minutes=4),
    )
    ready = system.mark_ready_for_manual_sending(
        record.task_id,
        actor_role="fictional_admin_reviewer",
        reason="human re-confirmed readiness",
        occurred_at=draft.created_at + timedelta(minutes=5),
    )
    assert ready.status is MockTaskStatus.READY_FOR_MANUAL_SENDING
    assert ready.message_sent is False
