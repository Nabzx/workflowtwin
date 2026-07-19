"""Contracts for deterministic product presentation and reset routes."""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "required_key"),
    [
        ("/api/v1/demo/overview", "journey"),
        ("/api/v1/demo/workflow", "nodes"),
        ("/api/v1/demo/metrics", "referral_sources"),
        ("/api/v1/demo/opportunity", "evidence_chain"),
        ("/api/v1/demo/simulation", "scenarios"),
        ("/api/v1/demo/engineering", "architecture"),
    ],
)
async def test_demo_read_contracts_are_fictional_and_path_free(
    client: AsyncClient, path: str, required_key: str
) -> None:
    response = await client.get(path)

    assert response.status_code == 200
    payload = response.json()
    assert required_key in payload
    assert payload["context"]["fictional_data"] is True
    assert "Northstar" in payload["context"]["declaration"]
    assert "/Users/" not in response.text
    assert "hidden_simulation_truth" not in response.text


@pytest.mark.anyio
async def test_workflow_contract_is_compact_and_connected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/demo/workflow")
    payload = response.json()
    node_ids = {node["id"] for node in payload["nodes"]}

    assert len(payload["nodes"]) == 12
    assert all(edge["source"] in node_ids for edge in payload["edges"])
    assert all(edge["target"] in node_ids for edge in payload["edges"])
    assert len(response.content) < 30_000


@pytest.mark.anyio
async def test_local_demo_reset_restores_deterministic_state(client: AsyncClient) -> None:
    before = (await client.get("/api/v1/pilot/summary")).json()
    response = await client.post("/api/v1/demo/reset", json={})
    after = (await client.get("/api/v1/pilot/summary")).json()

    assert response.status_code == 200
    assert response.json()["status"] == "reset"
    assert before == after


@pytest.mark.anyio
async def test_cors_allows_configured_local_frontend(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/demo/overview",
        headers={
            "origin": "http://localhost:5173",
            "access-control-request-method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.anyio
async def test_system_status_exposes_supported_versions_without_secrets(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/system/status")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ready"
    assert payload["demo_ready"] is True
    assert payload["detector_version"] == "completeness-review-detector-v1"
    assert payload["source_contract_version"] == "northstar-source-contract-v2"
    assert payload["fictional_data_mode"] is True
    assert "database_url" not in response.text
    assert response.headers["x-request-id"]
