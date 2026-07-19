"""Service lifecycle and status routes."""

from time import monotonic

from fastapi import APIRouter, Request

from workflowtwin import __version__
from workflowtwin.api.demo_schemas import SystemStatusResponse
from workflowtwin.api.schemas import HealthResponse, RootResponse
from workflowtwin.core.config import Settings
from workflowtwin.pilot.audit import verify_pilot_audit
from workflowtwin.pilot.models import PilotRun

router = APIRouter()


def _settings(request: Request) -> Settings:
    """Return settings attached by the application factory."""
    return request.app.state.settings  # type: ignore[no-any-return]


@router.get("/", response_model=RootResponse, tags=["service"])
async def root() -> RootResponse:
    """Describe the service and direct callers to its API documentation."""
    return RootResponse(
        service="WorkflowTwin API",
        version=__version__,
        message="Operational process intelligence for auditable workflow improvement.",
        docs_url="/docs",
    )


@router.get("/health", response_model=HealthResponse, tags=["service"])
async def health(request: Request) -> HealthResponse:
    """Report process liveness."""
    settings = _settings(request)
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=__version__,
        environment=settings.environment,
    )


@router.get("/ready", response_model=HealthResponse, tags=["service"])
async def ready(request: Request) -> HealthResponse:
    """Report readiness once deterministic demo state is available."""
    if not hasattr(request.app.state, "pilot_run"):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo unavailable"
        )
    return await health(request)


@router.get("/api/v1/system/status", response_model=SystemStatusResponse, tags=["service"])
async def system_status(request: Request) -> SystemStatusResponse:
    """Expose non-sensitive runtime and supported-product metadata."""
    run: PilotRun = request.app.state.pilot_run
    audit_valid, _ = verify_pilot_audit(request.app.state.pilot_service.audit_records)
    metadata = run.supported_detector_metadata
    return SystemStatusResponse(
        api_version="v1",
        application_version=__version__,
        status="ready" if audit_valid else "degraded",
        demo_ready=audit_valid,
        artefact_available=True,
        detector_version=str(metadata["product_name"]),
        source_contract_version=str(metadata["source_contract_version"]),
        database_status="configured_optional",
        uptime_seconds=monotonic() - request.app.state.started_at,
        pilot_artefact_fingerprint=run.run_fingerprint,
    )
