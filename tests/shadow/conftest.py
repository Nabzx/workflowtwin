"""Small deterministic shadow fixtures."""

from datetime import UTC, datetime

import pytest

from workflowtwin.shadow.config import DetectorProfile, ShadowConfig
from workflowtwin.shadow.intake import generate_intake_artifacts
from workflowtwin.shadow.models import IncomingReferralSnapshot, ShadowEvaluationLabel
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.models import GeneratedDataset
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset

ShadowSource = tuple[
    GeneratedDataset,
    tuple[IncomingReferralSnapshot, ...],
    tuple[ShadowEvaluationLabel, ...],
]


@pytest.fixture
def tiny_shadow_source() -> ShadowSource:
    dataset = SyntheticReferralGenerator(
        config_for_preset(
            GenerationPreset.TINY,
            case_count=40,
            seed=42,
            generation_run_id="shadow-test-source",
        ),
        generated_at=datetime(2026, 7, 18, tzinfo=UTC),
    ).generate()
    snapshots, labels = generate_intake_artifacts(dataset)
    return dataset, snapshots, labels


@pytest.fixture
def strict_shadow_config(tiny_shadow_source: ShadowSource) -> ShadowConfig:
    dataset = tiny_shadow_source[0]
    return ShadowConfig(
        shadow_run_id="shadow-test-strict",
        detector_profile=DetectorProfile.STRICT,
        source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
        generation_run_id=dataset.manifest.generation_run_id,
        opportunity_analysis_fingerprint="opportunity-fingerprint",
        simulation_analysis_fingerprint="simulation-fingerprint",
        minimum_evaluation_sample=3,
    )
