"""Stateful coordinator for human-reviewed fictional pilot actions."""

from datetime import datetime

from workflowtwin.core.fingerprint import stable_id
from workflowtwin.pilot.audit import append_audit
from workflowtwin.pilot.drafts import revise_draft
from workflowtwin.pilot.mock_system import InMemoryMockReferralSystem
from workflowtwin.pilot.models import (
    DraftMissingInformationRequest,
    DraftStatus,
    PilotAction,
    PilotActionStatus,
    PilotAuditRecord,
    PilotPolicy,
    PilotRecommendation,
    PilotReviewDecision,
    PilotReviewDecisionType,
    PilotRollback,
)
from workflowtwin.pilot.policy import validate_approval_preconditions


class PilotNotFoundError(LookupError):
    """Raised for an unknown recommendation, draft, review, or action."""


class PilotService:
    """Coordinate local pilot state while preserving human control and auditability."""

    def __init__(
        self,
        *,
        policy: PilotPolicy,
        recommendations: tuple[PilotRecommendation, ...],
        drafts: tuple[DraftMissingInformationRequest, ...],
        mock_system: InMemoryMockReferralSystem | None = None,
    ) -> None:
        self.policy = policy
        self.recommendations = {item.recommendation_id: item for item in recommendations}
        self.drafts = {item.draft_id: item for item in drafts}
        self.mock_system = mock_system or InMemoryMockReferralSystem()
        self.reviews: list[PilotReviewDecision] = []
        self.actions: list[PilotAction] = []
        self.rollbacks: list[PilotRollback] = []
        self.audit_records: tuple[PilotAuditRecord, ...] = ()
        for recommendation in sorted(recommendations, key=lambda item: item.recommendation_id):
            self._audit(
                occurred_at=recommendation.detected_at,
                actor_role="workflowtwin_system",
                action="recommendation_surfaced",
                object_id=recommendation.recommendation_id,
                input_references=recommendation.source_references,
                output_references=(recommendation.recommendation_id,),
            )
        for draft in sorted(drafts, key=lambda item: item.draft_id):
            self._audit(
                occurred_at=draft.created_at,
                actor_role="workflowtwin_system",
                action="draft_created",
                object_id=draft.draft_id,
                input_references=(draft.recommendation_id,),
                output_references=(draft.current_revision_id,),
            )

    def recommendation(self, recommendation_id: str) -> PilotRecommendation:
        try:
            return self.recommendations[recommendation_id]
        except KeyError as error:
            raise PilotNotFoundError("unknown pilot recommendation") from error

    def draft(self, draft_id: str) -> DraftMissingInformationRequest:
        try:
            return self.drafts[draft_id]
        except KeyError as error:
            raise PilotNotFoundError("unknown pilot draft") from error

    def edit_draft(
        self,
        draft_id: str,
        *,
        editor_role: str,
        revised_at: datetime,
        change_reason: str,
        heading: str | None = None,
        body: str | None = None,
    ) -> DraftMissingInformationRequest:
        updated = revise_draft(
            self.draft(draft_id),
            editor_role=editor_role,
            revised_at=revised_at,
            change_reason=change_reason,
            heading=heading,
            body=body,
        )
        self.drafts[draft_id] = updated
        self._audit(
            occurred_at=revised_at,
            actor_role=editor_role,
            action="draft_edited",
            object_id=draft_id,
            output_references=(updated.current_revision_id,),
            reason_codes=(change_reason,),
        )
        return updated

    def expire_due(self, *, as_of: datetime) -> tuple[str, ...]:
        expired: list[str] = []
        for draft_id, draft in sorted(self.drafts.items()):
            if draft.status in {DraftStatus.AWAITING_REVIEW, DraftStatus.EDITED} and (
                as_of >= draft.expires_at
            ):
                self.drafts[draft_id] = draft.model_copy(update={"status": DraftStatus.EXPIRED})
                expired.append(draft_id)
                self._audit(
                    occurred_at=as_of,
                    actor_role="workflowtwin_system",
                    action="draft_expired",
                    object_id=draft_id,
                    reason_codes=("review_window_elapsed",),
                )
        return tuple(expired)

    def retract(
        self,
        draft_id: str,
        *,
        retracted_at: datetime,
        actor_role: str,
        reason: str,
    ) -> DraftMissingInformationRequest:
        draft = self.draft(draft_id)
        if draft.status not in {
            DraftStatus.AWAITING_REVIEW,
            DraftStatus.EDITED,
            DraftStatus.APPROVED,
        }:
            raise ValueError("draft cannot be retracted in its current state")
        recommendation = self.recommendation(draft.recommendation_id)
        self.recommendations[recommendation.recommendation_id] = recommendation.model_copy(
            update={"current": False}
        )
        updated = draft.model_copy(update={"status": DraftStatus.RETRACTED})
        self.drafts[draft_id] = updated
        self._audit(
            occurred_at=retracted_at,
            actor_role=actor_role,
            action="draft_retracted",
            object_id=draft_id,
            input_references=(recommendation.snapshot_id,),
            reason_codes=(reason,),
        )
        return updated

    def review(
        self,
        draft_id: str,
        *,
        revision_id: str,
        reviewer_role: str,
        decision: PilotReviewDecisionType,
        decided_at: datetime,
        structured_reason: str,
        review_minutes: float,
    ) -> PilotReviewDecision:
        draft = self.draft(draft_id)
        recommendation = self.recommendation(draft.recommendation_id)
        policy_evaluation_id = validate_approval_preconditions(
            policy=self.policy,
            recommendation=recommendation,
            draft=draft,
            revision_id=revision_id,
            reviewer_role=reviewer_role,
            reviewed_at=decided_at,
        )
        review_id = stable_id("pilot-review", draft_id, revision_id, decision, reviewer_role)
        review = PilotReviewDecision(
            review_id=review_id,
            draft_id=draft_id,
            recommendation_id=recommendation.recommendation_id,
            revision_id=revision_id,
            reviewer_role=reviewer_role,
            decision=decision,
            decided_at=decided_at,
            structured_reason=structured_reason,
            policy_evaluation_id=policy_evaluation_id,
            review_minutes=review_minutes,
        )
        status = {
            PilotReviewDecisionType.APPROVE: DraftStatus.APPROVED,
            PilotReviewDecisionType.APPROVE_WITH_EDITS: DraftStatus.APPROVED,
            PilotReviewDecisionType.REJECT: DraftStatus.REJECTED,
            PilotReviewDecisionType.CANCEL: DraftStatus.CANCELLED,
            PilotReviewDecisionType.MARK_UNNECESSARY: DraftStatus.CLOSED,
            PilotReviewDecisionType.REQUEST_MORE_CONTEXT: DraftStatus.AWAITING_REVIEW,
        }[decision]
        self.reviews.append(review)
        self.drafts[draft_id] = draft.model_copy(update={"status": status})
        self._audit(
            occurred_at=decided_at,
            actor_role=reviewer_role,
            action=f"draft_review_{decision.value}",
            object_id=draft_id,
            input_references=(revision_id, policy_evaluation_id),
            output_references=(review_id,),
            reason_codes=(structured_reason,),
        )
        return review

    def commit_approved(self, draft_id: str, *, review_id: str, acted_at: datetime) -> PilotAction:
        draft = self.draft(draft_id)
        review = self._review(review_id)
        if draft.status not in {DraftStatus.APPROVED, DraftStatus.COMMITTED}:
            raise ValueError("pilot action requires an approved draft")
        if review.draft_id != draft_id or review.decision not in {
            PilotReviewDecisionType.APPROVE,
            PilotReviewDecisionType.APPROVE_WITH_EDITS,
        }:
            raise ValueError("pilot action requires a matching approval record")
        idempotency_key = stable_id(
            "pilot-action-idempotency",
            draft.recommendation_id,
            draft.current_revision_id,
            self.policy.policy_version,
            self.policy.action_type,
        )
        record, created = self.mock_system.create_task(
            draft=draft,
            idempotency_key=idempotency_key,
            actor_role=review.reviewer_role,
            occurred_at=acted_at,
        )
        action = PilotAction(
            action_id=stable_id("pilot-action", idempotency_key),
            idempotency_key=idempotency_key,
            recommendation_id=draft.recommendation_id,
            draft_id=draft_id,
            revision_id=draft.current_revision_id,
            review_id=review_id,
            action_type=self.policy.action_type,
            status=(
                PilotActionStatus.COMMITTED if created else PilotActionStatus.DUPLICATE_SUPPRESSED
            ),
            mock_task_id=record.task_id,
            acted_at=acted_at,
            actor_role=review.reviewer_role,
        )
        self.actions.append(action)
        if created:
            self.drafts[draft_id] = draft.model_copy(update={"status": DraftStatus.COMMITTED})
        self._audit(
            occurred_at=acted_at,
            actor_role=review.reviewer_role,
            action=action.status.value,
            object_id=action.action_id,
            input_references=(review_id, draft.current_revision_id),
            output_references=(record.task_id,),
        )
        return action

    def rollback(
        self,
        action_id: str,
        *,
        actor_role: str,
        reason: str,
        rolled_back_at: datetime,
    ) -> PilotRollback:
        action = self._action(action_id)
        if action.mock_task_id is None:
            raise ValueError("pilot action has no mock task to roll back")
        record, changed = self.mock_system.rollback_task(
            action.mock_task_id,
            actor_role=actor_role,
            reason=reason,
            occurred_at=rolled_back_at,
        )
        rollback_id = stable_id("pilot-rollback", action.action_id)
        existing = next((item for item in self.rollbacks if item.rollback_id == rollback_id), None)
        rollback = PilotRollback(
            rollback_id=rollback_id,
            action_id=action.action_id,
            mock_task_id=record.task_id,
            actor_role=actor_role if existing is None else existing.actor_role,
            reason=reason if existing is None else existing.reason,
            rolled_back_at=rolled_back_at if existing is None else existing.rolled_back_at,
            restored_status=record.status,
            duplicate_request=not changed,
        )
        if existing is None:
            self.rollbacks.append(rollback)
            self.drafts[action.draft_id] = self.draft(action.draft_id).model_copy(
                update={"status": DraftStatus.ROLLED_BACK}
            )
        self._audit(
            occurred_at=rolled_back_at,
            actor_role=actor_role,
            action="rollback_completed" if changed else "duplicate_rollback_suppressed",
            object_id=rollback_id,
            input_references=(action_id,),
            output_references=(record.task_id,),
            reason_codes=(reason,),
        )
        return rollback

    def _review(self, review_id: str) -> PilotReviewDecision:
        review = next((item for item in self.reviews if item.review_id == review_id), None)
        if review is None:
            raise PilotNotFoundError("unknown pilot review")
        return review

    def _action(self, action_id: str) -> PilotAction:
        action = next((item for item in self.actions if item.action_id == action_id), None)
        if action is None:
            raise PilotNotFoundError("unknown pilot action")
        return action

    def _audit(
        self,
        *,
        occurred_at: datetime,
        actor_role: str,
        action: str,
        object_id: str,
        input_references: tuple[str, ...] = (),
        output_references: tuple[str, ...] = (),
        reason_codes: tuple[str, ...] = (),
    ) -> None:
        self.audit_records = append_audit(
            self.audit_records,
            occurred_at=occurred_at,
            actor_role=actor_role,
            action=action,
            object_id=object_id,
            input_references=input_references,
            output_references=output_references,
            reason_codes=reason_codes,
        )
