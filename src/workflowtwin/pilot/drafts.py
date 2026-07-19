"""Deterministic administrative-only pilot draft generation and revision."""

from datetime import datetime, timedelta

from workflowtwin.core.fingerprint import stable_id
from workflowtwin.pilot.models import (
    DraftItem,
    DraftMissingInformationRequest,
    DraftRevision,
    DraftStatus,
    PilotRecommendation,
)
from workflowtwin.source_contracts.models import FORBIDDEN_TERMS, IncomingReferralSnapshotV2

HEADING = "Administrative information review"
HUMAN_WARNING = "Human review is required. This fictional draft has not been sent."
DISPLAY_NAMES = {
    "supporting_document": "Supporting document confirmation",
    "source_acknowledgement": "Referrer acknowledgement",
    "routing_contact": "Administrative reply route",
    "referral_form": "Referral form confirmation",
}


def _body(items: tuple[DraftItem, ...]) -> str:
    bullets = "\n".join(f"- {item.display_name}" for item in items)
    return (
        "The submitted referral appears to be missing the following required administrative "
        f"items:\n\n{bullets}\n\nPlease verify these items before any external request is "
        f"prepared.\n\n{HUMAN_WARNING}"
    )


def _validate_text(*values: str) -> None:
    content = " ".join(values).lower()
    if any(term in content for term in FORBIDDEN_TERMS):
        raise ValueError("pilot draft contains prohibited clinical or identifying content")


def create_draft(
    *,
    recommendation: PilotRecommendation,
    snapshot: IncomingReferralSnapshotV2,
    actor_role: str = "workflowtwin_system",
) -> DraftMissingInformationRequest:
    items = tuple(
        DraftItem(
            field_id=field_id,
            display_name=DISPLAY_NAMES[field_id],
            requirement_id=next(
                reference
                for reference in recommendation.requirement_references
                if field_id.replace("_", "-") in reference
                or field_id == "supporting_document"
            ),
        )
        for field_id in recommendation.missing_field_ids
    )
    heading = HEADING
    body = _body(items)
    _validate_text(heading, body, *(item.display_name for item in items))
    draft_id = stable_id("pilot-draft", recommendation.recommendation_id)
    revision_id = stable_id("draft-revision", draft_id, 1)
    audit_reference = stable_id("pilot-audit-reference", revision_id)
    revision = DraftRevision(
        revision_id=revision_id,
        previous_revision_id=None,
        editor_role=actor_role,
        revised_at=recommendation.detected_at,
        change_reason="initial_deterministic_template",
        changed_fields=("heading", "body", "items"),
        heading=heading,
        body=body,
        items=items,
        audit_reference=audit_reference,
    )
    return DraftMissingInformationRequest(
        draft_id=draft_id,
        recommendation_id=recommendation.recommendation_id,
        case_id=recommendation.case_id,
        administrative_recipient_role="fictional_referring_organisation_admin",
        form_version=snapshot.form_version,
        source_snapshot_references=recommendation.source_references,
        requirements_contract_references=recommendation.requirement_references,
        created_at=recommendation.detected_at,
        expires_at=recommendation.detected_at + timedelta(hours=8),
        status=DraftStatus.AWAITING_REVIEW,
        current_revision_id=revision_id,
        revisions=(revision,),
    )


def revise_draft(
    draft: DraftMissingInformationRequest,
    *,
    editor_role: str,
    revised_at: datetime,
    change_reason: str,
    heading: str | None = None,
    body: str | None = None,
) -> DraftMissingInformationRequest:
    if draft.status not in {DraftStatus.AWAITING_REVIEW, DraftStatus.EDITED}:
        raise ValueError("draft cannot be edited in its current state")
    current = next(
        item for item in draft.revisions if item.revision_id == draft.current_revision_id
    )
    next_heading = heading if heading is not None else current.heading
    next_body = body if body is not None else current.body
    _validate_text(next_heading, next_body)
    changed = tuple(
        name
        for name, before, after in (
            ("heading", current.heading, next_heading),
            ("body", current.body, next_body),
        )
        if before != after
    )
    if not changed:
        raise ValueError("draft edit contains no changes")
    revision_id = stable_id("draft-revision", draft.draft_id, len(draft.revisions) + 1)
    revision = DraftRevision(
        revision_id=revision_id,
        previous_revision_id=current.revision_id,
        editor_role=editor_role,
        revised_at=revised_at,
        change_reason=change_reason,
        changed_fields=changed,
        heading=next_heading,
        body=next_body,
        items=current.items,
        audit_reference=stable_id("pilot-audit-reference", revision_id),
    )
    return draft.model_copy(
        update={
            "status": DraftStatus.EDITED,
            "current_revision_id": revision_id,
            "revisions": (*draft.revisions, revision),
        }
    )
