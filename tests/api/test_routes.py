"""Contract tests for service endpoints."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from workflowtwin import __version__
from workflowtwin.core.config import Settings
from workflowtwin.main import create_app


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


@pytest.mark.anyio
async def test_readiness_reports_seeded_demo(client: AsyncClient) -> None:
    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_unified_deployment_serves_spa_without_swallowing_api(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (tmp_path / "index.html").write_text("<main>WorkflowTwin frontend</main>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('ready')", encoding="utf-8")
    settings = Settings(_env_file=None, environment="test", web_dist_path=tmp_path)
    transport = ASGITransport(app=create_app(settings))

    async with AsyncClient(transport=transport, base_url="http://test") as deployed:
        root = await deployed.get("/")
        client_route = await deployed.get("/workflow")
        api = await deployed.get("/api/v1/demo/overview")
        missing_asset = await deployed.get("/missing.png")

    assert "WorkflowTwin frontend" in root.text
    assert "WorkflowTwin frontend" in client_route.text
    assert api.json()["context"]["fictional_data"] is True
    assert missing_asset.status_code == 404
