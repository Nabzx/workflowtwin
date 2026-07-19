"""Local-only API routes for the fictional human-approved pilot."""

from fastapi import APIRouter, HTTPException, Request, status

from workflowtwin.api.pilot_schemas import (
    DraftApprovalRequest,
    DraftDecisionRequest,
    DraftEditRequest,
    PilotSummaryResponse,
    ReviewRequest,
    RollbackRequest,
)
from workflowtwin.pilot.models import (
    DraftMissingInformationRequest,
    PilotAction,
    PilotAuditRecord,
    PilotGateResult,
    PilotRecommendation,
    PilotReviewDecision,
    PilotReviewDecisionType,
    PilotRollback,
    PilotRun,
)
from workflowtwin.pilot.service import PilotNotFoundError, PilotService

router = APIRouter(prefix="/api/v1/pilot", tags=["fictional-pilot"])


def _state(request: Request) -> tuple[PilotRun, PilotService]:
    run: PilotRun = request.app.state.pilot_run
    service: PilotService = request.app.state.pilot_service
    return run, service


def _translate_error(error: Exception) -> HTTPException:
    if isinstance(error, PilotNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.get("/summary", response_model=PilotSummaryResponse)
async def summary(request: Request) -> PilotSummaryResponse:
    run, _ = _state(request)
    return PilotSummaryResponse(
        run_id=run.run_id,
        policy_version=run.policy.policy_version,
        detector_name=str(run.supported_detector_metadata["product_name"]),
        detector_lineage=str(run.supported_detector_metadata["derived_from"]),
        assessment=run.assessment,
        metrics=run.metrics,
        gates=run.gates,
        fictional_declaration=run.fictional_declaration,
    )


@router.get("/recommendations", response_model=tuple[PilotRecommendation, ...])
async def recommendations(request: Request) -> tuple[PilotRecommendation, ...]:
    _, service = _state(request)
    return tuple(service.recommendations[key] for key in sorted(service.recommendations))


@router.get("/recommendations/{recommendation_id}", response_model=PilotRecommendation)
async def recommendation(request: Request, recommendation_id: str) -> PilotRecommendation:
    _, service = _state(request)
    try:
        return service.recommendation(recommendation_id)
    except PilotNotFoundError as error:
        raise _translate_error(error) from error


@router.post(
    "/recommendations/{recommendation_id}/review",
    response_model=PilotReviewDecision,
)
async def review_recommendation(
    request: Request, recommendation_id: str, payload: ReviewRequest
) -> PilotReviewDecision:
    _, service = _state(request)
    try:
        recommendation = service.recommendation(recommendation_id)
        draft = next(
            item
            for item in service.drafts.values()
            if item.recommendation_id == recommendation.recommendation_id
        )
        return service.review(
            draft.draft_id,
            revision_id=payload.revision_id,
            reviewer_role=payload.reviewer_role,
            decision=payload.decision,
            decided_at=payload.decided_at,
            structured_reason=payload.structured_reason,
            review_minutes=payload.review_minutes,
        )
    except (PilotNotFoundError, PermissionError, StopIteration, ValueError) as error:
        translated = (
            PilotNotFoundError("recommendation has no pilot draft")
            if isinstance(error, StopIteration)
            else error
        )
        raise _translate_error(translated) from error


@router.get("/drafts", response_model=tuple[DraftMissingInformationRequest, ...])
async def drafts(request: Request) -> tuple[DraftMissingInformationRequest, ...]:
    _, service = _state(request)
    return tuple(service.drafts[key] for key in sorted(service.drafts))


@router.get("/drafts/{draft_id}", response_model=DraftMissingInformationRequest)
async def draft(request: Request, draft_id: str) -> DraftMissingInformationRequest:
    _, service = _state(request)
    try:
        return service.draft(draft_id)
    except PilotNotFoundError as error:
        raise _translate_error(error) from error


@router.post("/drafts/{draft_id}/edit", response_model=DraftMissingInformationRequest)
async def edit_draft(
    request: Request, draft_id: str, payload: DraftEditRequest
) -> DraftMissingInformationRequest:
    _, service = _state(request)
    try:
        return service.edit_draft(
            draft_id,
            editor_role=payload.editor_role,
            revised_at=payload.revised_at,
            change_reason=payload.change_reason,
            heading=payload.heading,
            body=payload.body,
        )
    except (PilotNotFoundError, ValueError) as error:
        raise _translate_error(error) from error


def _decide(
    service: PilotService,
    draft_id: str,
    payload: DraftDecisionRequest,
    decision: PilotReviewDecisionType,
) -> PilotReviewDecision:
    return service.review(
        draft_id,
        revision_id=payload.revision_id,
        reviewer_role=payload.reviewer_role,
        decision=decision,
        decided_at=payload.decided_at,
        structured_reason=payload.structured_reason,
        review_minutes=payload.review_minutes,
    )


def _restore_revision(
    service: PilotService, draft_id: str, payload: DraftApprovalRequest
) -> None:
    draft = service.draft(draft_id)
    if draft.current_revision_id == payload.revision_id:
        return
    replay = payload.revision_replay
    if replay is None:
        raise ValueError("review targets a stale draft revision")
    updated = service.edit_draft(
        draft_id,
        editor_role=replay.editor_role,
        revised_at=replay.revised_at,
        change_reason=replay.change_reason,
        heading=replay.heading,
        body=replay.body,
    )
    if updated.current_revision_id != payload.revision_id:
        raise ValueError("revision replay did not match the reviewed revision")


@router.post("/drafts/{draft_id}/approve", response_model=PilotAction)
async def approve_draft(
    request: Request, draft_id: str, payload: DraftApprovalRequest
) -> PilotAction:
    _, service = _state(request)
    try:
        _restore_revision(service, draft_id, payload)
        review = _decide(service, draft_id, payload, PilotReviewDecisionType.APPROVE)
        return service.commit_approved(
            draft_id, review_id=review.review_id, acted_at=payload.decided_at
        )
    except (PilotNotFoundError, PermissionError, ValueError) as error:
        raise _translate_error(error) from error


@router.post("/drafts/{draft_id}/reject", response_model=PilotReviewDecision)
async def reject_draft(
    request: Request, draft_id: str, payload: DraftDecisionRequest
) -> PilotReviewDecision:
    _, service = _state(request)
    try:
        return _decide(service, draft_id, payload, PilotReviewDecisionType.REJECT)
    except (PilotNotFoundError, PermissionError, ValueError) as error:
        raise _translate_error(error) from error


@router.post("/drafts/{draft_id}/cancel", response_model=PilotReviewDecision)
async def cancel_draft(
    request: Request, draft_id: str, payload: DraftDecisionRequest
) -> PilotReviewDecision:
    _, service = _state(request)
    try:
        return _decide(service, draft_id, payload, PilotReviewDecisionType.CANCEL)
    except (PilotNotFoundError, PermissionError, ValueError) as error:
        raise _translate_error(error) from error


@router.post("/drafts/{draft_id}/rollback", response_model=PilotRollback)
async def rollback_draft(
    request: Request, draft_id: str, payload: RollbackRequest
) -> PilotRollback:
    _, service = _state(request)
    try:
        service.draft(draft_id)
        action = next(
            (
                item
                for item in reversed(service.actions)
                if item.draft_id == draft_id and item.mock_task_id is not None
            ),
            None,
        )
        if action is None and payload.action_replay is not None:
            expected = payload.action_replay
            draft = service.draft(draft_id)
            if draft.current_revision_id != expected.revision_id:
                service.edit_draft(
                    draft_id,
                    editor_role=expected.actor_role,
                    revised_at=expected.acted_at,
                    change_reason="Verified ephemeral rollback replay",
                    heading="Administrative supporting document check",
                )
            review = service.review(
                draft_id,
                revision_id=expected.revision_id,
                reviewer_role=expected.actor_role,
                decision=PilotReviewDecisionType.APPROVE,
                decided_at=expected.acted_at,
                structured_reason="Verified fictional action replay for rollback",
                review_minutes=0,
            )
            action = service.commit_approved(
                draft_id, review_id=review.review_id, acted_at=expected.acted_at
            )
            if (
                action.action_id != expected.action_id
                or action.idempotency_key != expected.idempotency_key
                or action.mock_task_id != expected.mock_task_id
            ):
                raise PermissionError("action replay did not match the approved fictional action")
        if action is None:
            raise PilotNotFoundError("draft has no committed pilot action")
        return service.rollback(
            action.action_id,
            actor_role=payload.actor_role,
            reason=payload.reason,
            rolled_back_at=payload.rolled_back_at,
        )
    except (PilotNotFoundError, PermissionError, ValueError) as error:
        raise _translate_error(error) from error


@router.get("/audit", response_model=tuple[PilotAuditRecord, ...])
async def audit(request: Request) -> tuple[PilotAuditRecord, ...]:
    _, service = _state(request)
    return service.audit_records


@router.get("/gates", response_model=tuple[PilotGateResult, ...])
async def gates(request: Request) -> tuple[PilotGateResult, ...]:
    run, _ = _state(request)
    return run.gates
