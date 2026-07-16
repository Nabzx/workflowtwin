"""Small documented generation presets."""

from enum import StrEnum
from typing import Any

from workflowtwin.synthetic.config import GenerationConfig


class GenerationPreset(StrEnum):
    TINY = "tiny"
    DEMO = "demo"
    FULL = "full"


PRESET_CASE_COUNTS = {
    GenerationPreset.TINY: 30,
    GenerationPreset.DEMO: 1_000,
    GenerationPreset.FULL: 10_000,
}


def config_for_preset(preset: GenerationPreset, **overrides: Any) -> GenerationConfig:
    """Create a fully revalidated configuration for a named preset."""
    values = GenerationConfig(case_count=PRESET_CASE_COUNTS[preset]).model_dump()
    values.update(overrides)
    return GenerationConfig.model_validate(values)
