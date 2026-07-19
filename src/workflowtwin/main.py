"""FastAPI application factory and default ASGI application."""

from time import monotonic

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from workflowtwin import __version__
from workflowtwin.api.demo_routes import router as demo_router
from workflowtwin.api.pilot_routes import router as pilot_router
from workflowtwin.api.routes import router
from workflowtwin.core.config import Settings, get_settings
from workflowtwin.core.logging import configure_logging
from workflowtwin.core.observability import request_observability
from workflowtwin.pilot.demo import build_demo_pilot


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an application with explicit, testable runtime settings."""
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings)

    application = FastAPI(
        title="WorkflowTwin API",
        summary="Operational process intelligence and workflow improvement API",
        description=(
            "WorkflowTwin analyses administrative workflows. Northstar Clinics and all "
            "initial data are fictional; the service does not make clinical decisions."
        ),
        version=__version__,
    )
    application.state.settings = runtime_settings
    application.state.started_at = monotonic()
    pilot_run, pilot_service = build_demo_pilot()
    application.state.pilot_run = pilot_run
    application.state.pilot_service = pilot_service
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["content-type", "x-request-id"],
    )
    application.middleware("http")(request_observability)
    application.include_router(router)
    application.include_router(demo_router)
    application.include_router(pilot_router)

    structlog.get_logger(__name__).info(
        "application_configured",
        environment=runtime_settings.environment,
        version=__version__,
    )
    return application


app = create_app()
