"""Typed reader for compact immutable detector experiment goldens."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class HistoricalMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    incoming_cases: int = Field(ge=1)
    detector_positives: int = Field(ge=0)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    false_positive_review_hours: float = Field(ge=0)
    detector_positive_coverage: float = Field(ge=0, le=1)
    surfaced_coverage: float | None = Field(default=None, ge=0, le=1)


class HistoricalDetectorGolden(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detector_version: str
    configuration_fingerprint: str = Field(min_length=64, max_length=64)
    source_contract_fingerprint: str
    input_fixture_fingerprint: str = Field(min_length=64, max_length=64)
    recommendation_identifiers: tuple[str, ...]
    headline_metrics: HistoricalMetrics
    assessment_result: str
    evaluation_fingerprint: str = Field(min_length=64, max_length=64)
    fictional: bool = True


def load_detector_golden(path: Path) -> HistoricalDetectorGolden:
    """Load historical evidence without importing an obsolete detector runtime."""
    return HistoricalDetectorGolden.model_validate_json(path.read_text(encoding="utf-8"))
