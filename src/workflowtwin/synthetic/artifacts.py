"""Safe JSON artifact export and import for synthetic generation."""

import json
from pathlib import Path
from typing import Any

from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent
from workflowtwin.synthetic.config import GenerationConfig
from workflowtwin.synthetic.models import (
    DatasetValidationReport,
    GeneratedDataset,
    GenerationGroundTruth,
    GenerationManifest,
)


class ArtifactExistsError(FileExistsError):
    """Raised when safe output would overwrite an existing artifact."""


def _write_json(path: Path, value: Any, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ArtifactExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def write_manifest(path: Path, manifest: GenerationManifest, *, overwrite: bool = False) -> None:
    _write_json(path, manifest.model_dump(mode="json"), overwrite=overwrite)


def write_ground_truth(
    path: Path, ground_truth: GenerationGroundTruth, *, overwrite: bool = False
) -> None:
    _write_json(path, ground_truth.model_dump(mode="json"), overwrite=overwrite)


def write_validation_report(
    path: Path, report: DatasetValidationReport, *, overwrite: bool = False
) -> None:
    _write_json(path, report.model_dump(mode="json"), overwrite=overwrite)


def write_dataset(path: Path, dataset: GeneratedDataset, *, overwrite: bool = False) -> None:
    """Export a development bundle; large bundles remain ignored by Git."""
    payload = {
        "configuration": dataset.config.model_dump(mode="json"),
        "cases": [case.model_dump(mode="json") for case in dataset.cases],
        "events": [event.model_dump(mode="json") for event in dataset.events],
        "ground_truth": dataset.ground_truth.model_dump(mode="json"),
        "manifest": dataset.manifest.model_dump(mode="json"),
    }
    _write_json(path, payload, overwrite=overwrite)


def load_dataset(path: Path) -> GeneratedDataset:
    """Load and revalidate a previously exported development bundle."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("dataset artifact must contain a JSON object")
    return GeneratedDataset(
        config=GenerationConfig.model_validate(payload["configuration"]),
        cases=tuple(ReferralCase.model_validate(case) for case in payload["cases"]),
        events=tuple(ReferralEvent.model_validate(event) for event in payload["events"]),
        ground_truth=GenerationGroundTruth.model_validate(payload["ground_truth"]),
        manifest=GenerationManifest.model_validate(payload["manifest"]),
    )


def load_manifest(path: Path) -> GenerationManifest:
    """Load and validate a standalone generation manifest."""
    return GenerationManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_ground_truth(path: Path) -> GenerationGroundTruth:
    """Load and validate a standalone synthetic benchmark label file."""
    return GenerationGroundTruth.model_validate_json(path.read_text(encoding="utf-8"))
