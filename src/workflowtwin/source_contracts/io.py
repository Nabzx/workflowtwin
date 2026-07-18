"""Validated source-contract loading and atomic artifact output."""

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from workflowtwin.source_contracts.models import (
    IncomingReferralSnapshotV2,
    SourceContractDefinition,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.synthetic.artifacts import ArtifactExistsError

_SNAPSHOTS = TypeAdapter(tuple[IncomingReferralSnapshotV2, ...])


def load_source_contract(path: Path) -> SourceContractDefinition:
    return SourceContractDefinition.model_validate_json(path.read_text(encoding="utf-8"))


def load_requirements(path: Path) -> AdministrativeRequirementsContract:
    return AdministrativeRequirementsContract.model_validate_json(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise ArtifactExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_v2_jsonl(
    path: Path,
    snapshots: tuple[IncomingReferralSnapshotV2, ...],
    *,
    overwrite: bool = False,
) -> None:
    if path.exists() and not overwrite:
        raise ArtifactExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "\n".join(json.dumps(item.model_dump(mode="json"), sort_keys=True) for item in snapshots)
        + ("\n" if snapshots else ""),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_v2_jsonl(path: Path) -> tuple[IncomingReferralSnapshotV2, ...]:
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return _SNAPSHOTS.validate_python(values)
