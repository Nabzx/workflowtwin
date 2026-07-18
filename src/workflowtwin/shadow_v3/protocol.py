"""Strict-v3 protocol loading, validation lock, and single-use holdout registry."""

import json
from datetime import UTC, datetime
from pathlib import Path

from workflowtwin.shadow.fingerprint import shadow_fingerprint
from workflowtwin.shadow_v3.config import StrictV3Config
from workflowtwin.shadow_v3.models import (
    StrictV3Lock,
    StrictV3Protocol,
    V3Evaluation,
    V3HoldoutRegistry,
)
from workflowtwin.synthetic.artifacts import ArtifactExistsError


def load_v3_protocol(path: Path) -> StrictV3Protocol:
    return StrictV3Protocol.model_validate_json(path.read_text(encoding="utf-8"))


def validate_protocol_locks(protocol: StrictV3Protocol, config: StrictV3Config) -> None:
    expected = {
        "detector_version": config.detector_version,
        "source_contract_version": config.source_contract_version,
        "source_contract_fingerprint": config.source_contract_fingerprint,
        "requirements_contract_version": config.requirements_contract_version,
        "requirements_contract_fingerprint": config.requirements_contract_fingerprint,
        "capacity_fingerprint": config.capacity_fingerprint,
        "policy_fingerprint": config.policy_fingerprint,
        "detector_fingerprint": config.detector_fingerprint,
        "rule_lock_version": config.rule_lock_version,
    }
    for field, value in expected.items():
        if getattr(protocol, field) != value:
            raise ValueError(f"strict-v3 protocol lock mismatch: {field}")


def write_v3_protocol(path: Path, protocol: StrictV3Protocol, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise ArtifactExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(protocol.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def lock_after_validation(
    *,
    protocol: StrictV3Protocol,
    config: StrictV3Config,
    validation: V3Evaluation,
    path: Path,
) -> StrictV3Lock:
    validate_protocol_locks(protocol, config)
    if validation.promotion_assessment != "eligible_for_holdout":
        raise ValueError("strict_v3_validation_failed")
    content = {
        "protocol_id": protocol.protocol_id,
        "detector_fingerprint": config.detector_fingerprint,
        "policy_fingerprint": config.policy_fingerprint,
        "source_contract_fingerprint": config.source_contract_fingerprint,
        "requirements_contract_fingerprint": config.requirements_contract_fingerprint,
        "capacity_fingerprint": config.capacity_fingerprint,
        "validation_evaluation_fingerprint": validation.evaluation_fingerprint,
        "validation_assessment": validation.promotion_assessment,
        "locked_at": datetime(2026, 7, 18, 12, tzinfo=UTC),
    }
    lock = StrictV3Lock.model_validate({**content, "lock_fingerprint": shadow_fingerprint(content)})
    if path.exists():
        existing = StrictV3Lock.model_validate_json(path.read_text(encoding="utf-8"))
        if existing != lock:
            raise ValueError("strict-v3 lock already exists with different content")
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(lock.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return lock


def begin_v3_holdout(
    *,
    protocol: StrictV3Protocol,
    config: StrictV3Config,
    lock: StrictV3Lock,
    registry_path: Path,
) -> V3HoldoutRegistry:
    validate_protocol_locks(protocol, config)
    expected = (
        config.detector_fingerprint,
        config.policy_fingerprint,
        config.source_contract_fingerprint,
        config.requirements_contract_fingerprint,
        config.capacity_fingerprint,
    )
    actual = (
        lock.detector_fingerprint,
        lock.policy_fingerprint,
        lock.source_contract_fingerprint,
        lock.requirements_contract_fingerprint,
        lock.capacity_fingerprint,
    )
    if actual != expected or lock.validation_assessment != "eligible_for_holdout":
        raise ValueError("strict-v3 holdout lock is incompatible or validation did not pass")
    if registry_path.exists():
        registry = V3HoldoutRegistry.model_validate_json(registry_path.read_text(encoding="utf-8"))
        if (
            registry.detector_fingerprint,
            registry.policy_fingerprint,
            registry.source_contract_fingerprint,
            registry.requirements_contract_fingerprint,
            registry.capacity_fingerprint,
            registry.lock_fingerprint,
        ) != (*expected, lock.lock_fingerprint):
            raise ValueError("holdout V3 already opened with incompatible locks")
        return registry
    registry = V3HoldoutRegistry(
        protocol_id=protocol.protocol_id,
        dataset_id=protocol.holdout_dataset.dataset_id,
        detector_fingerprint=config.detector_fingerprint,
        policy_fingerprint=config.policy_fingerprint,
        source_contract_fingerprint=config.source_contract_fingerprint,
        requirements_contract_fingerprint=config.requirements_contract_fingerprint,
        capacity_fingerprint=config.capacity_fingerprint,
        lock_fingerprint=lock.lock_fingerprint,
        evaluation_count=1,
        evaluation_fingerprint=None,
        status="started",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return registry


def complete_v3_holdout(
    registry: V3HoldoutRegistry,
    evaluation: V3Evaluation,
    *,
    registry_path: Path,
) -> V3HoldoutRegistry:
    if registry.status == "completed":
        if registry.evaluation_fingerprint != evaluation.evaluation_fingerprint:
            raise ValueError("immutable holdout V3 result fingerprint mismatch")
        return registry
    completed = registry.model_copy(
        update={
            "status": "completed",
            "evaluation_fingerprint": evaluation.evaluation_fingerprint,
        }
    )
    temporary = registry_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(completed.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(registry_path)
    return completed
