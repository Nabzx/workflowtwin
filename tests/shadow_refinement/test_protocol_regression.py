"""Frozen detector identity and holdout governance regression tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.intake import generate_intake_artifacts
from workflowtwin.shadow.models import RecommendationStatus
from workflowtwin.shadow.runner import ShadowModeRunner
from workflowtwin.shadow_refinement.config import StrictV2Config
from workflowtwin.shadow_refinement.protocol import (
    begin_holdout,
    complete_holdout,
    load_refinement_protocol,
)
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


def test_strict_v1_demo_regression_is_frozen() -> None:
    dataset = SyntheticReferralGenerator(
        config_for_preset(GenerationPreset.DEMO, seed=42),
        generated_at=datetime(2026, 7, 18, tzinfo=UTC),
    ).generate()
    snapshots, _ = generate_intake_artifacts(dataset)
    run = ShadowModeRunner(
        ShadowConfig(
            shadow_run_id="strict-v1-regression",
            detector_version="strict-v1",
            source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
            generation_run_id=dataset.manifest.generation_run_id,
            opportunity_analysis_fingerprint="regression",
            simulation_analysis_fingerprint="regression",
        )
    ).run(snapshots)
    created = [item for item in run.recommendations if item.status is RecommendationStatus.CREATED]
    assert len(created) == 195
    assert {item.reason_codes for item in created} == {("required_supporting_document_absent",)}


def test_holdout_registry_is_single_use_and_detector_locked(tmp_path: Path) -> None:
    protocol = load_refinement_protocol(Path("config/shadow/refinement-protocol.json"))
    path = tmp_path / "registry.json"
    fingerprint = StrictV2Config().detector_fingerprint
    started = begin_holdout(protocol=protocol, detector_fingerprint=fingerprint, registry_path=path)
    assert started.evaluation_count == 1
    completed = complete_holdout(started, evaluation_fingerprint="result-1", registry_path=path)
    assert completed.status == "completed"
    assert (
        begin_holdout(protocol=protocol, detector_fingerprint=fingerprint, registry_path=path)
        == completed
    )
    with pytest.raises(ValueError, match="incompatible detector"):
        begin_holdout(
            protocol=protocol, detector_fingerprint="changed-detector", registry_path=path
        )
