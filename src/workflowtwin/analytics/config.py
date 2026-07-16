"""Validated configuration for operational baseline analysis."""

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

AnalysisIdentifier = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$", max_length=64)
]


class DuplicatePolicy(StrEnum):
    DEDUPLICATE = "deduplicate_source_identity"
    REJECT = "reject_duplicate_source_identity"


class CohortDimension(StrEnum):
    REFERRAL_SOURCE = "referral_source"
    SERVICE_LINE = "service_line"
    SOURCE_SYSTEM = "source_system"
    ASSIGNED_TEAM = "assigned_team"
    TERMINAL_OUTCOME = "terminal_outcome"


class AnalysisConfig(BaseModel):
    """Meaningful analytical choices, independent of output transport."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: AnalysisIdentifier = "northstar-baseline-v1"
    expected_schema_version: int = Field(default=1, ge=1)
    period_start: datetime | None = None
    period_end: datetime | None = None
    analysis_cutoff: datetime = datetime(2027, 1, 31, tzinfo=UTC)
    reporting_timezone: str = "Europe/London"
    stuck_threshold_hours: float = Field(default=120, gt=0)
    working_hour_start: int = Field(default=8, ge=0, le=23)
    working_hour_end: int = Field(default=18, ge=1, le=24)
    skip_weekends: bool = True
    include_open_cases: bool = True
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.DEDUPLICATE
    delayed_ingestion_threshold_hours: float = Field(default=24, gt=0)
    cohort_dimensions: tuple[CohortDimension, ...] = tuple(CohortDimension)
    minimum_cohort_size: int = Field(default=20, ge=2)
    percentiles: tuple[float, ...] = (0.5, 0.75, 0.9, 0.95)
    manual_touch_minutes_proxy: float = Field(default=10, gt=0)
    relative_materiality_threshold: float = Field(default=0.20, gt=0)
    absolute_rate_materiality_threshold: float = Field(default=0.10, gt=0, le=1)
    report_output: Path | None = None
    analysis_output: Path | None = None
    case_metrics_output: Path | None = None
    source_dataset_fingerprint: str | None = None
    generation_run_id: str | None = None

    @field_validator("period_start", "period_end", "analysis_cutoff")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("analysis timestamps must be timezone-aware")
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
    def validate_analysis_window(self) -> Self:
        if self.period_start and self.period_end and self.period_end <= self.period_start:
            raise ValueError("period_end must be later than period_start")
        if self.period_end and self.analysis_cutoff < self.period_end:
            raise ValueError("analysis_cutoff cannot be earlier than period_end")
        if self.working_hour_end <= self.working_hour_start:
            raise ValueError("working_hour_end must be later than working_hour_start")
        if not self.percentiles or tuple(sorted(set(self.percentiles))) != self.percentiles:
            raise ValueError("percentiles must be unique and sorted")
        if any(percentile <= 0 or percentile >= 1 for percentile in self.percentiles):
            raise ValueError("percentiles must be between 0 and 1")
        return self
