"""Draft safety, revision, policy, and pilot audit tests."""

from datetime import timedelta

import pytest

from workflowtwin.pilot.audit import append_audit, verify_pilot_audit
from workflowtwin.pilot.drafts import HUMAN_WARNING, create_draft, revise_draft
from workflowtwin.pilot.models import PilotRecommendation
from workflowtwin.pilot.policy import load_pilot_policy, validate_approval_preconditions
from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2


def test_draft_is_deterministic_administrative_and_unsent(
    pilot_recommendation: PilotRecommendation,
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    snapshot = v2_source[0][0]
    first = create_draft(recommendation=pilot_recommendation, snapshot=snapshot)
    second = create_draft(recommendation=pilot_recommendation, snapshot=snapshot)
    assert first == second
    assert first.no_message_sent is True
    assert first.human_review_required is True
    assert first.revisions[0].items[0].field_id == "supporting_document"
    assert HUMAN_WARNING in first.revisions[0].body
    assert first.source_snapshot_references
    assert first.requirements_contract_references == ("supporting-document",)


def test_edit_is_append_only_and_rejects_clinical_or_empty_changes(
    pilot_recommendation: PilotRecommendation,
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    draft = create_draft(recommendation=pilot_recommendation, snapshot=v2_source[0][0])
    edited = revise_draft(
        draft,
        editor_role="fictional_admin_reviewer",
        revised_at=draft.created_at + timedelta(minutes=3),
        change_reason="clarify administrative wording",
        heading="Administrative document check",
    )
    assert len(edited.revisions) == 2
    assert edited.revisions[1].previous_revision_id == edited.revisions[0].revision_id
    assert draft.revisions == (draft.revisions[0],)
    with pytest.raises(ValueError, match="no changes"):
        revise_draft(
            edited,
            editor_role="fictional_admin_reviewer",
            revised_at=edited.created_at + timedelta(minutes=4),
            change_reason="nothing changed",
        )
    with pytest.raises(ValueError, match="prohibited"):
        revise_draft(
            edited,
            editor_role="fictional_admin_reviewer",
            revised_at=edited.created_at + timedelta(minutes=5),
            change_reason="invalid content",
            body="Add a diagnosis to this request",
        )


def test_approval_preconditions_enforce_role_revision_and_conflicts(
    pilot_recommendation: PilotRecommendation,
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    policy = load_pilot_policy()
    draft = create_draft(recommendation=pilot_recommendation, snapshot=v2_source[0][0])
    evaluation_id = validate_approval_preconditions(
        policy=policy,
        recommendation=pilot_recommendation,
        draft=draft,
        revision_id=draft.current_revision_id,
        reviewer_role="fictional_admin_reviewer",
    )
    assert evaluation_id.startswith("pilot-policy-evaluation-")
    with pytest.raises(PermissionError, match="not permitted"):
        validate_approval_preconditions(
            policy=policy,
            recommendation=pilot_recommendation,
            draft=draft,
            revision_id=draft.current_revision_id,
            reviewer_role="unauthorised",
        )
    with pytest.raises(ValueError, match="stale"):
        validate_approval_preconditions(
            policy=policy,
            recommendation=pilot_recommendation,
            draft=draft,
            revision_id="old-revision",
            reviewer_role="fictional_admin_reviewer",
        )
    with pytest.raises(ValueError, match="conflict"):
        validate_approval_preconditions(
            policy=policy,
            recommendation=pilot_recommendation.model_copy(
                update={"unresolved_source_conflict": True}
            ),
            draft=draft,
            revision_id=draft.current_revision_id,
            reviewer_role="fictional_admin_reviewer",
        )


def test_pilot_audit_chain_detects_tampering(
    pilot_recommendation: PilotRecommendation,
) -> None:
    records = append_audit(
        (),
        occurred_at=pilot_recommendation.detected_at,
        actor_role="workflowtwin_system",
        action="recommendation_surfaced",
        object_id=pilot_recommendation.recommendation_id,
    )
    records = append_audit(
        records,
        occurred_at=pilot_recommendation.detected_at + timedelta(minutes=1),
        actor_role="fictional_admin_reviewer",
        action="draft_reviewed",
        object_id="draft-test",
        input_references=(records[0].audit_id,),
    )
    assert verify_pilot_audit(records) == (True, 0)
    changed = records[1].model_copy(update={"action": "changed"})
    assert verify_pilot_audit((records[0], changed)) == (False, 1)
