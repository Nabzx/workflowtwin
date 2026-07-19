"""Versioned pilot policy loading and human-approval preconditions."""

from datetime import datetime
from pathlib import Path

from workflowtwin.core.fingerprint import fingerprint, stable_id
from workflowtwin.pilot.models import (
    DraftMissingInformationRequest,
    DraftStatus,
    PilotPolicy,
    PilotRecommendation,
)

DEFAULT_PILOT_POLICY_PATH = Path("config/pilot/northstar-fictional-pilot-policy-v1.json")


def load_pilot_policy(path: Path = DEFAULT_PILOT_POLICY_PATH) -> PilotPolicy:
    return PilotPolicy.model_validate_json(path.read_text(encoding="utf-8"))


def pilot_policy_fingerprint(policy: PilotPolicy) -> str:
    return fingerprint(policy)


def validate_approval_preconditions(
    *,
    policy: PilotPolicy,
    recommendation: PilotRecommendation,
    draft: DraftMissingInformationRequest,
    revision_id: str,
    reviewer_role: str,
    reviewed_at: datetime | None = None,
) -> str:
    if reviewer_role not in policy.permitted_reviewer_roles:
        raise PermissionError("reviewer role is not permitted by the fictional pilot policy")
    if not recommendation.current:
        raise ValueError("recommendation is no longer current")
    if recommendation.unresolved_source_conflict:
        raise ValueError("recommendation has an unresolved source conflict")
    if draft.status not in {DraftStatus.AWAITING_REVIEW, DraftStatus.EDITED}:
        raise ValueError("draft is not awaiting a review decision")
    if draft.current_revision_id != revision_id:
        raise ValueError("review targets a stale draft revision")
    if reviewed_at is not None and reviewed_at >= draft.expires_at:
        raise ValueError("draft has expired")
    if not recommendation.source_references or not recommendation.requirement_references:
        raise ValueError("recommendation provenance is incomplete")
    return stable_id(
        "pilot-policy-evaluation",
        policy.policy_version,
        recommendation.recommendation_id,
        draft.draft_id,
        revision_id,
        reviewer_role,
    )
