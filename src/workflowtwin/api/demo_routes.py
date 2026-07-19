"""Read-only product demo routes and guarded reset operation."""

import hmac

from fastapi import APIRouter, HTTPException, Request, status

from workflowtwin.api.demo_schemas import (
    DemoResetRequest,
    DemoResetResponse,
    EngineeringResponse,
    MetricsResponse,
    OpportunityResponse,
    OverviewResponse,
    SimulationResponse,
    WorkflowResponse,
)
from workflowtwin.demo import repository
from workflowtwin.pilot.demo import build_demo_pilot

router = APIRouter(prefix="/api/v1/demo", tags=["fictional-demo"])


@router.get("/overview", response_model=OverviewResponse)
async def overview() -> OverviewResponse:
    return repository.overview()


@router.get("/workflow", response_model=WorkflowResponse)
async def workflow() -> WorkflowResponse:
    return repository.workflow()


@router.get("/metrics", response_model=MetricsResponse)
async def metrics() -> MetricsResponse:
    return repository.metrics()


@router.get("/opportunity", response_model=OpportunityResponse)
async def opportunity() -> OpportunityResponse:
    return repository.opportunity()


@router.get("/simulation", response_model=SimulationResponse)
async def simulation() -> SimulationResponse:
    return repository.simulation()


@router.get("/engineering", response_model=EngineeringResponse)
async def engineering() -> EngineeringResponse:
    return repository.engineering()


@router.post("/reset", response_model=DemoResetResponse)
async def reset_demo(request: Request, payload: DemoResetRequest) -> DemoResetResponse:
    settings = request.app.state.settings
    allowed = settings.environment in {"local", "test"}
    if settings.demo_reset_token:
        allowed = payload.token is not None and hmac.compare_digest(
            payload.token, settings.demo_reset_token
        )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo reset is disabled or requires the configured reset token.",
        )
    run, service = build_demo_pilot()
    request.app.state.pilot_run = run
    request.app.state.pilot_service = service
    return DemoResetResponse(run_id=run.run_id, declaration=run.fictional_declaration)
