"""Strict-v3 pre-registration, evaluation, lock, and holdout safeguards."""

from pathlib import Path

import pytest

from workflowtwin.services.shadow_v3 import run_v3_holdout, run_v3_validation
from workflowtwin.shadow_v3.config import StrictV3Config
from workflowtwin.shadow_v3.models import (
    SourceQualityGates,
    StrictV3Protocol,
    V3DatasetRole,
    V3DatasetSpecification,
    V3Evaluation,
    V3Thresholds,
)
from workflowtwin.shadow_v3.protocol import load_v3_protocol, validate_protocol_locks
from workflowtwin.source_contracts.io import load_requirements, load_source_contract


def _spec(
    dataset_id: str, role: V3DatasetRole, seed: int, cases: int
) -> V3DatasetSpecification:
    return V3DatasetSpecification(
        dataset_id=dataset_id,
        role=role,
        seed=seed,
        case_count=cases,
        operating_days=20,
        generation_run_id=f"tiny-{dataset_id}",
    )


def _passing_protocol() -> StrictV3Protocol:
    protocol = load_v3_protocol(Path("config/shadow/strict-v3-protocol.json"))
    return protocol.model_copy(
        update={
            "protocol_id": "tiny-v3-protocol",
            "validation_dataset": _spec("tiny-v3-validation", V3DatasetRole.VALIDATION, 901, 60),
            "holdout_dataset": _spec("tiny-v3-holdout", V3DatasetRole.HOLDOUT, 902, 70),
            "thresholds": V3Thresholds(
                minimum_precision=0,
                minimum_recall=0,
                minimum_ceiling_relative_recall=0,
                maximum_false_positive_hours_per_100_cases=100,
                maximum_detector_positive_coverage=1,
                maximum_surfaced_coverage=1,
                maximum_p95_recommendation_latency_minutes=1000,
                minimum_audit_completeness=1,
                minimum_policy_compliance=1,
            ),
            "source_quality_gates": SourceQualityGates(
                minimum_supported_form_rate=0,
                minimum_applicability_coverage=0,
                minimum_requirements_version_agreement=0,
                minimum_usable_input_coverage=0,
                maximum_stale_snapshot_rate=1,
                maximum_conflict_rate=1,
            ),
        }
    )


@pytest.mark.parametrize(
    ("changed_field", "expected_mismatch"),
    [
        ("source_contract_fingerprint", "source_contract_fingerprint"),
        ("requirements_contract_fingerprint", "requirements_contract_fingerprint"),
        ("capacity_fingerprint", "capacity_fingerprint"),
        ("policy_version", "policy_fingerprint"),
        ("detector_rule_version", "detector_fingerprint"),
    ],
)
def test_registered_protocol_matches_every_runtime_lock(
    changed_field: str, expected_mismatch: str
) -> None:
    protocol = load_v3_protocol(Path("config/shadow/strict-v3-protocol.json"))
    config = StrictV3Config()
    validate_protocol_locks(protocol, config)
    assert protocol.holdout_dataset.seed == 808
    assert protocol.holdout_evaluation_count == 0
    with pytest.raises(ValueError, match=expected_mismatch):
        validate_protocol_locks(
            protocol,
            config.model_copy(update={changed_field: "changed"}),
        )


def test_validation_lock_and_holdout_registry_are_single_use(tmp_path: Path) -> None:
    protocol = _passing_protocol()
    config = StrictV3Config()
    definition = load_source_contract(Path("config/shadow/source-contract-v2.json"))
    requirements = load_requirements(Path("config/shadow/northstar-requirements-v2.json"))
    lock_path = tmp_path / "strict-v3-lock.json"
    validation = run_v3_validation(
        protocol=protocol,
        config=config,
        definition=definition,
        requirements=requirements,
        output_path=tmp_path / "validation.json",
        report_path=tmp_path / "validation.md",
        lock_path=lock_path,
    )
    assert validation.promotion_assessment == "eligible_for_holdout"
    assert lock_path.exists()
    def evaluate_holdout() -> V3Evaluation | None:
        return run_v3_holdout(
            protocol=protocol,
            config=config,
            definition=definition,
            requirements=requirements,
            lock_path=lock_path,
            registry_path=tmp_path / "holdout-registry.json",
            output_path=tmp_path / "holdout.json",
            report_path=tmp_path / "holdout.md",
        )

    assert evaluate_holdout() is not None
    assert evaluate_holdout() is None
    registry = (tmp_path / "holdout-registry.json").read_text(encoding="utf-8")
    assert '"evaluation_count": 1' in registry
    assert '"status": "completed"' in registry


def test_failed_validation_cannot_create_a_lock(tmp_path: Path) -> None:
    protocol = load_v3_protocol(Path("config/shadow/strict-v3-protocol.json"))
    config = StrictV3Config()
    definition = load_source_contract(Path("config/shadow/source-contract-v2.json"))
    requirements = load_requirements(Path("config/shadow/northstar-requirements-v2.json"))
    failed_protocol = protocol.model_copy(
        update={
            "validation_dataset": _spec("failing-v3-validation", V3DatasetRole.VALIDATION, 903, 50),
            "thresholds": protocol.thresholds.model_copy(
                update={"minimum_precision": 1.0, "minimum_recall": 1.0}
            ),
        }
    )
    evaluation = run_v3_validation(
        protocol=failed_protocol,
        config=config,
        definition=definition,
        requirements=requirements,
        output_path=tmp_path / "failed.json",
        report_path=tmp_path / "failed.md",
        lock_path=tmp_path / "must-not-exist.json",
    )
    assert evaluation.promotion_assessment == "strict_v3_validation_failed"
    assert not (tmp_path / "must-not-exist.json").exists()
