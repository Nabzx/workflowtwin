"""Shared deterministic synthetic datasets."""

from datetime import UTC, datetime

import pytest

from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.models import GeneratedDataset
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


@pytest.fixture(scope="module")
def demo_dataset() -> GeneratedDataset:
    config = config_for_preset(GenerationPreset.DEMO, seed=42)
    return SyntheticReferralGenerator(
        config, generated_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
    ).generate()
