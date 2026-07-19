"""Versioned API contracts for the fictional local pilot."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from workflowtwin.pilot.models import (
    PilotAction,
    PilotAssessment,
    PilotGateResult,
    PilotMetrics,
    PilotReviewDecisionType,
)


class PilotApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PilotSummaryResponse(PilotApiModel):
    run_id: str
    policy_version: str
    detector_name: str
    detector_lineage: str
    assessment: PilotAssessment
    metrics: PilotMetrics
    gates: tuple[PilotGateResult, ...]
    fictional_declaration: str
    no_message_sent: bool = True


class ReviewRequest(PilotApiModel):
    revision_id: str
    reviewer_role: str
    decision: PilotReviewDecisionType
    decided_at: datetime
    structured_reason: str = Field(min_length=3, max_length=240)
    review_minutes: float = Field(ge=0, le=240)


class DraftEditRequest(PilotApiModel):
    editor_role: str
    revised_at: datetime
    change_reason: str = Field(min_length=3, max_length=240)
    heading: str | None = Field(default=None, min_length=3, max_length=120)
    body: str | None = Field(default=None, min_length=3, max_length=2000)


class DraftDecisionRequest(PilotApiModel):
    revision_id: str
    reviewer_role: str
    decided_at: datetime
    structured_reason: str = Field(min_length=3, max_length=240)
    review_minutes: float = Field(ge=0, le=240)


class DraftApprovalRequest(DraftDecisionRequest):
    revision_replay: DraftEditRequest | None = None


class RollbackRequest(PilotApiModel):
    actor_role: str
    rolled_back_at: datetime
    reason: str = Field(min_length=3, max_length=240)
    action_replay: PilotAction | None = None
