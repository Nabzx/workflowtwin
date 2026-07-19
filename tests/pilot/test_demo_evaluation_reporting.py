"""Deterministic supported pilot pipeline and policy evidence tests."""

import json
from pathlib import Path

import pytest

from workflowtwin.pilot.demo import build_demo_pilot
from workflowtwin.pilot.evaluation import evaluate_gates
from workflowtwin.pilot.models import PilotAssessment, PilotReviewDecisionType
from workflowtwin.pilot.reporting import render_pilot_report, write_pilot_artifacts


def test_demo_pilot_is_deterministic_policy_compliant_and_local() -> None:
    first, _ = build_demo_pilot()
    second, _ = build_demo_pilot()
    assert first == second
    assert first.assessment is PilotAssessment.READY_FOR_FICTIONAL_PILOT_DEMO
    assert first.stop_conditions == ()
    assert first.metrics.detector_positive_coverage > first.metrics.surfaced_recommendation_coverage
    assert first.metrics.surfaced_recommendation_coverage <= 0.2
    assert first.metrics.detector_precision is not None
    assert first.metrics.detector_precision >= 0.9
    assert first.metrics.detector_recall is not None
    assert first.metrics.detector_recall >= 0.72
    assert all(item.message_sent is False for item in first.mock_records)
    assert all(item.operational_events_mutated is False for item in first.actions)
    approvals = {
        item.review_id
        for item in first.reviews
        if item.decision
        in {PilotReviewDecisionType.APPROVE, PilotReviewDecisionType.APPROVE_WITH_EDITS}
    }
    assert all(item.review_id in approvals for item in first.actions)


def test_safety_gate_failure_pauses_pilot() -> None:
    run, _ = build_demo_pilot()
    unsafe = run.metrics.model_copy(update={"external_communication_attempts": 1})
    gates, failures, assessment = evaluate_gates(unsafe, run.policy)
    assert "safety-external-communication" in failures
    assert assessment is PilotAssessment.PAUSE_DUE_TO_STOP_CONDITION
    assert next(item for item in gates if item.gate_id in failures).status == "fail"


def test_pilot_artifacts_are_small_explicit_and_protected(tmp_path: Path) -> None:
    output = tmp_path
    run, _ = build_demo_pilot()
    json_path, report_path = write_pilot_artifacts(run, output)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")
    assert payload["fictional_declaration"].startswith("Fictional Northstar")
    assert payload["supported_detector_metadata"]["derived_from"] == "strict-v3"
    assert "strict_v3_validation_failed" in report
    assert "No message was sent" in report
    assert render_pilot_report(run) == report
    with pytest.raises(FileExistsError, match="--reset"):
        write_pilot_artifacts(run, output)
