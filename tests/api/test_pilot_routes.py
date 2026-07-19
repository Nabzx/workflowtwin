"""Integration tests for the fictional local pilot API."""

from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from workflowtwin.core.config import Settings
from workflowtwin.main import create_app


async def _awaiting_draft(client: AsyncClient) -> dict[str, object]:
    response = await client.get("/api/v1/pilot/drafts")
    assert response.status_code == 200
    return next(item for item in response.json() if item["status"] == "draft_awaiting_review")


def _decision(
    draft: dict[str, object], *, role: str = "fictional_admin_reviewer"
) -> dict[str, object]:
    decided_at = datetime.fromisoformat(str(draft["created_at"])) + timedelta(minutes=15)
    return {
        "revision_id": draft["current_revision_id"],
        "reviewer_role": role,
        "decided_at": decided_at.isoformat(),
        "structured_reason": "administrative evidence checked",
        "review_minutes": 4,
    }


@pytest.mark.anyio
async def test_summary_lists_supported_path_and_transparent_workload(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pilot/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["detector_name"] == "completeness-review-detector-v1"
    assert payload["detector_lineage"] == "strict-v3"
    assert payload["assessment"] == "ready_for_fictional_pilot_demo"
    assert payload["no_message_sent"] is True
    assert (
        payload["metrics"]["detector_positive_coverage"]
        > payload["metrics"]["surfaced_recommendation_coverage"]
    )
    assert all(item["status"] == "pass" for item in payload["gates"])


@pytest.mark.anyio
async def test_recommendation_list_read_review_and_invalid_identifier(
    client: AsyncClient,
) -> None:
    listed = await client.get("/api/v1/pilot/recommendations")
    recommendation = listed.json()[0]
    read = await client.get(f"/api/v1/pilot/recommendations/{recommendation['recommendation_id']}")
    assert read.status_code == 200
    assert read.json() == recommendation
    missing = await client.get("/api/v1/pilot/recommendations/not-real")
    assert missing.status_code == 404

    draft = await _awaiting_draft(client)
    payload = _decision(draft)
    payload["decision"] = "request_more_context"
    reviewed = await client.post(
        f"/api/v1/pilot/recommendations/{draft['recommendation_id']}/review",
        json=payload,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["decision"] == "request_more_context"


@pytest.mark.anyio
async def test_edit_and_approve_create_only_a_local_human_approved_task(
    client: AsyncClient,
) -> None:
    draft = await _awaiting_draft(client)
    revised_at = datetime.fromisoformat(str(draft["created_at"])) + timedelta(minutes=2)
    edited = await client.post(
        f"/api/v1/pilot/drafts/{draft['draft_id']}/edit",
        json={
            "editor_role": "fictional_admin_reviewer",
            "revised_at": revised_at.isoformat(),
            "change_reason": "clearer administrative heading",
            "heading": "Administrative document confirmation",
        },
    )
    assert edited.status_code == 200
    current = edited.json()
    assert len(current["revisions"]) == 2
    approved = await client.post(
        f"/api/v1/pilot/drafts/{draft['draft_id']}/approve",
        json=_decision(current),
    )
    assert approved.status_code == 200
    action = approved.json()
    assert action["status"] == "committed_to_mock_system"
    assert action["no_external_communication"] is True
    assert action["operational_events_mutated"] is False
    audit = await client.get("/api/v1/pilot/audit")
    assert audit.status_code == 200
    assert audit.json()[-1]["action"] == "committed_to_mock_system"


@pytest.mark.anyio
async def test_reject_cancel_policy_failure_and_clinical_edit_are_explicit(
    client: AsyncClient,
) -> None:
    draft = await _awaiting_draft(client)
    rejected = await client.post(
        f"/api/v1/pilot/drafts/{draft['draft_id']}/reject",
        json=_decision(draft),
    )
    assert rejected.status_code == 200
    assert rejected.json()["decision"] == "reject"

    another = await _awaiting_draft(client)
    forbidden = await client.post(
        f"/api/v1/pilot/drafts/{another['draft_id']}/cancel",
        json=_decision(another, role="not_permitted"),
    )
    assert forbidden.status_code == 403
    clinical = await client.post(
        f"/api/v1/pilot/drafts/{another['draft_id']}/edit",
        json={
            "editor_role": "fictional_admin_reviewer",
            "revised_at": (
                datetime.fromisoformat(str(another["created_at"])) + timedelta(minutes=1)
            ).isoformat(),
            "change_reason": "invalid content",
            "body": "Please infer a diagnosis",
        },
    )
    assert clinical.status_code == 409
    assert "prohibited" in clinical.json()["detail"]


@pytest.mark.anyio
async def test_rollback_and_gate_endpoints(client: AsyncClient) -> None:
    drafts = (await client.get("/api/v1/pilot/drafts")).json()
    committed = next(
        item for item in drafts if item["status"] == "draft_committed_to_fictional_task_queue"
    )
    rolled_back_at = datetime.fromisoformat(committed["created_at"]) + timedelta(minutes=20)
    response = await client.post(
        f"/api/v1/pilot/drafts/{committed['draft_id']}/rollback",
        json={
            "actor_role": "fictional_pilot_supervisor",
            "rolled_back_at": rolled_back_at.isoformat(),
            "reason": "API rollback verification",
        },
    )
    assert response.status_code == 200
    assert response.json()["restored_status"] == "rolled_back"
    gates = await client.get("/api/v1/pilot/gates")
    assert gates.status_code == 200
    assert len(gates.json()) >= 20


@pytest.mark.anyio
async def test_ephemeral_instances_replay_bounded_revision_and_action() -> None:
    settings = Settings(_env_file=None, environment="production", log_level="ERROR")

    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)), base_url="http://edit-instance"
    ) as edit_instance:
        draft = await _awaiting_draft(edit_instance)
        revised_at = datetime.fromisoformat(str(draft["created_at"])) + timedelta(minutes=2)
        edit_payload = {
            "editor_role": "fictional_admin_reviewer",
            "revised_at": revised_at.isoformat(),
            "change_reason": "clearer administrative heading",
            "heading": "Administrative document confirmation",
        }
        edited = await edit_instance.post(
            f"/api/v1/pilot/drafts/{draft['draft_id']}/edit", json=edit_payload
        )
        current = edited.json()

    approval_payload = _decision(current)
    approval_payload["revision_replay"] = edit_payload
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)), base_url="http://approval-instance"
    ) as approval_instance:
        approved = await approval_instance.post(
            f"/api/v1/pilot/drafts/{draft['draft_id']}/approve", json=approval_payload
        )
        action = approved.json()

    assert approved.status_code == 200
    assert action["revision_id"] == current["current_revision_id"]
    async with AsyncClient(
        transport=ASGITransport(app=create_app(settings)), base_url="http://rollback-instance"
    ) as rollback_instance:
        rolled_back = await rollback_instance.post(
            f"/api/v1/pilot/drafts/{draft['draft_id']}/rollback",
            json={
                "actor_role": "fictional_pilot_supervisor",
                "rolled_back_at": (
                    datetime.fromisoformat(action["acted_at"]) + timedelta(minutes=3)
                ).isoformat(),
                "reason": "ephemeral deployment verification",
                "action_replay": action,
            },
        )

    assert rolled_back.status_code == 200
    assert rolled_back.json()["action_id"] == action["action_id"]
