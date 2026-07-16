"""Foundation API routes."""

from fastapi import APIRouter, Request

from workflowtwin import __version__
from workflowtwin.api.schemas import HealthResponse, RootResponse
from workflowtwin.core.config import Settings

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
    """Report process liveness; dependency readiness is added with database use."""
    settings = _settings(request)
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=__version__,
        environment=settings.environment,
    )
