"""Validated configuration for Northstar process reconstruction."""

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from workflowtwin.analytics.config import DuplicatePolicy

ProcessAnalysisIdentifier = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$", max_length=64)
]


class ConformanceMethod(StrEnum):
    TOKEN_REPLAY = "token_based_replay"


class EventOrderingPolicy(StrEnum):
    EVENT_TIME = "event_at_then_event_id"


class TieBreakingPolicy(StrEnum):
    EVENT_ID = "lexicographic_event_id"


class ProcessMiningConfig(BaseModel):
    """Analytical choices independent of PM4Py objects and output transport."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: ProcessAnalysisIdentifier = "northstar-process-v1"
    expected_schema_version: int = Field(default=1, ge=1)
    source_dataset_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    baseline_analysis_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    generation_run_id: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    reporting_timezone: str = "Europe/London"
    activity_mapping_version: str = "northstar-activity-map-v1"
    ordering_policy: EventOrderingPolicy = EventOrderingPolicy.EVENT_TIME
    tie_breaking_policy: TieBreakingPolicy = TieBreakingPolicy.EVENT_ID
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.DEDUPLICATE
    minimum_variant_frequency: int = Field(default=2, ge=1)
    maximum_reported_variants: int = Field(default=20, ge=1, le=500)
    rare_variant_case_threshold: int = Field(default=2, ge=1)
    minimum_transition_frequency: int = Field(default=5, ge=1)
    minimum_cohort_size: int = Field(default=20, ge=2)
    duration_percentiles: tuple[float, ...] = (0.5, 0.75, 0.9, 0.95)
    conformance_method: ConformanceMethod = ConformanceMethod.TOKEN_REPLAY
    conformance_timeout_seconds: float = Field(default=120, gt=0)
    maximum_conformance_cases: int = Field(default=10_000, ge=1)
    strict_reference_enabled: bool = True
    governed_reference_enabled: bool = True
    discovery_noise_threshold: float = Field(default=0.0, ge=0, le=1)
    visualisation_minimum_frequency: int = Field(default=5, ge=1)
    visualisation_maximum_edges: int = Field(default=100, ge=1, le=2_000)
    analysis_output: Path | None = None
    report_output: Path | None = None
    graph_output: Path | None = None
    case_output: Path | None = None
    visualisation_directory: Path | None = None
    overwrite: bool = False

    @field_validator("period_start", "period_end")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("process-analysis timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("reporting_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown IANA timezone: {value}") from error
        return value

    @model_validator(mode="after")
    def validate_choices(self) -> Self:
        if self.period_start and self.period_end and self.period_end <= self.period_start:
            raise ValueError("period_end must be later than period_start")
        if not self.strict_reference_enabled and not self.governed_reference_enabled:
            raise ValueError("at least one reference workflow must be enabled")
        if tuple(sorted(set(self.duration_percentiles))) != self.duration_percentiles:
            raise ValueError("duration_percentiles must be unique and sorted")
        if not self.duration_percentiles or any(
            percentile <= 0 or percentile >= 1 for percentile in self.duration_percentiles
        ):
            raise ValueError("duration_percentiles must be between 0 and 1")
        if self.rare_variant_case_threshold > self.minimum_variant_frequency:
            raise ValueError("rare_variant_case_threshold cannot exceed minimum_variant_frequency")
        return self
