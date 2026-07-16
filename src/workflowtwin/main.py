"""FastAPI application factory and default ASGI application."""

import structlog
from fastapi import FastAPI

from workflowtwin import __version__
from workflowtwin.api.routes import router
from workflowtwin.core.config import Settings, get_settings
from workflowtwin.core.logging import configure_logging


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
    application.include_router(router)

    structlog.get_logger(__name__).info(
        "application_configured",
        environment=runtime_settings.environment,
        version=__version__,
    )
    return application


app = create_app()
