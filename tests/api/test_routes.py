"""Contract tests for service endpoints."""

import pytest
from httpx import AsyncClient

from workflowtwin import __version__


@pytest.mark.anyio
async def test_root_describes_service(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "WorkflowTwin API",
        "version": __version__,
        "message": "Operational process intelligence for auditable workflow improvement.",
        "docs_url": "/docs",
    }


@pytest.mark.anyio
async def test_health_reports_liveness_and_environment(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "workflowtwin-api-test",
        "version": __version__,
        "environment": "test",
    }
