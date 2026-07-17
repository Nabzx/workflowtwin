"""Application orchestration for file and read-only PostgreSQL shadow sources."""

import json
from pathlib import Path
from typing import cast

from workflowtwin.shadow.config import DetectorProfile, ShadowConfig
from workflowtwin.shadow.intake import generate_intake_artifacts, load_intake_snapshots
from workflowtwin.shadow.models import IncomingReferralSnapshot, ReplayCheckpoint, ShadowRun
from workflowtwin.shadow.runner import ShadowModeRunner
from workflowtwin.synthetic.artifacts import load_dataset, load_manifest


def _fingerprint_from_json(path: Path, key: str) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get(key), str):
        raise ValueError(f"{path} does not contain {key}")
    return cast(str, payload[key])


def build_shadow_config(
    *,
    run_id: str,
    profile: DetectorProfile,
    manifest_path: Path,
    opportunity_path: Path,
    simulation_path: Path,
    overwrite: bool = False,
    **updates: object,
) -> ShadowConfig:
    manifest = load_manifest(manifest_path)
    return ShadowConfig.model_validate(
        {
            "shadow_run_id": run_id,
            "detector_profile": profile,
            "source_dataset_fingerprint": manifest.dataset_fingerprint,
            "generation_run_id": manifest.generation_run_id,
            "opportunity_analysis_fingerprint": _fingerprint_from_json(
                opportunity_path, "opportunity_analysis_fingerprint"
            ),
            "simulation_analysis_fingerprint": _fingerprint_from_json(
                simulation_path, "simulation_analysis_fingerprint"
            ),
            "overwrite": overwrite,
            **updates,
        }
    )


def load_or_generate_snapshots(
    *, dataset_path: Path, snapshots_path: Path | None
) -> tuple[IncomingReferralSnapshot, ...]:
    if snapshots_path is not None:
        return load_intake_snapshots(snapshots_path)
    dataset = load_dataset(dataset_path)
    snapshots, _ = generate_intake_artifacts(dataset)
    return snapshots


def run_shadow(
    *,
    config: ShadowConfig,
    snapshots: tuple[IncomingReferralSnapshot, ...],
    checkpoint_path: Path | None = None,
    max_source_items: int | None = None,
) -> ShadowRun:
    checkpoint = (
        ReplayCheckpoint.model_validate_json(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint_path
        else None
    )
    return ShadowModeRunner(config).run(
        snapshots, checkpoint=checkpoint, max_source_items=max_source_items
    )
