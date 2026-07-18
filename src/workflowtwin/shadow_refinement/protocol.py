"""Machine-readable refinement protocol and holdout evaluation registry."""

import json
from pathlib import Path

from workflowtwin.shadow_refinement.fingerprint import locked_fingerprint
from workflowtwin.shadow_refinement.models import HoldoutRegistry, RefinementProtocol
from workflowtwin.synthetic.artifacts import ArtifactExistsError


def load_refinement_protocol(path: Path) -> RefinementProtocol:
    return RefinementProtocol.model_validate_json(path.read_text(encoding="utf-8"))


def protocol_fingerprint(protocol: RefinementProtocol) -> str:
    return locked_fingerprint(protocol)


def begin_holdout(
    *,
    protocol: RefinementProtocol,
    detector_fingerprint: str,
    registry_path: Path,
) -> HoldoutRegistry:
    if registry_path.exists():
        registry = HoldoutRegistry.model_validate_json(registry_path.read_text(encoding="utf-8"))
        if registry.detector_fingerprint == detector_fingerprint:
            return registry
        raise ValueError("holdout was already opened with an incompatible detector lock")
    registry = HoldoutRegistry(
        protocol_id=protocol.protocol_id,
        dataset_id=protocol.holdout_dataset.dataset_id,
        detector_version=protocol.candidate_detector_version,
        detector_fingerprint=detector_fingerprint,
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


def complete_holdout(
    registry: HoldoutRegistry,
    *,
    evaluation_fingerprint: str,
    registry_path: Path,
) -> HoldoutRegistry:
    if registry.status == "completed":
        if registry.evaluation_fingerprint != evaluation_fingerprint:
            raise ValueError("idempotent holdout rerun produced a different fingerprint")
        return registry
    completed = registry.model_copy(
        update={"evaluation_fingerprint": evaluation_fingerprint, "status": "completed"}
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = registry_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(completed.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(registry_path)
    return completed


def write_protocol(path: Path, protocol: RefinementProtocol, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise ArtifactExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(protocol.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
