"""Validated configuration for deterministic referral generation."""

from datetime import UTC, datetime
from enum import StrEnum
from math import isclose
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

from workflowtwin.domain.referrals.enums import ReferralSource, ServiceLine, SourceSystem

Probability = Annotated[float, Field(ge=0.0, le=1.0)]
RunIdentifier = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$", max_length=64),
]


class OutputMode(StrEnum):
    """Whether generation remains in memory or is intended for artifact export."""

    MEMORY = "memory"
    ARTIFACTS = "artifacts"


class ConfigModel(BaseModel):
    """Strict immutable configuration base."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DurationRange(ConfigModel):
    """Inclusive uniform duration range measured in hours."""

    minimum: float = Field(ge=0)
    maximum: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.maximum < self.minimum:
            raise ValueError("duration maximum must be greater than or equal to minimum")
        return self


class OutcomeRates(ConfigModel):
    """Mutually exclusive intended case outcomes."""

    completed: Probability = 0.82
    cancelled: Probability = 0.08
    rejected: Probability = 0.05
    stuck: Probability = 0.05

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        total = self.completed + self.cancelled + self.rejected + self.stuck
        if not isclose(total, 1.0, abs_tol=1e-9):
            raise ValueError(f"outcome rates must sum to 1.0, received {total:.6f}")
        return self


class DeviationRates(ConfigModel):
    """Background workflow deviation and valid data-quality rates."""

    initially_incomplete: Probability = 0.20
    repeated_missing_information: Probability = 0.18
    recategorisation: Probability = 0.08
    team_reassignment: Probability = 0.10
    failed_scheduling: Probability = 0.12
    patient_non_response: Probability = 0.06
    repeated_completeness_check: Probability = 0.07
    duplicate_source_event: Probability = 0.025
    delayed_ingestion: Probability = 0.05
    out_of_order_ingestion: Probability = 0.035
    missing_optional_actor: Probability = 0.025
    unexpected_channel: Probability = 0.02
    source_identifier_inconsistency: Probability = 0.015
    source_retry: Probability = 0.015


def _default_source_system_mix() -> dict[SourceSystem, float]:
    return {
        SourceSystem.REFERRAL_PORTAL: 0.60,
        SourceSystem.SECURE_EMAIL: 0.25,
        SourceSystem.MANUAL_ENTRY: 0.15,
    }


def _default_referral_source_mix() -> dict[ReferralSource, float]:
    return {
        ReferralSource.GP_PRACTICE: 0.42,
        ReferralSource.COMMUNITY_CLINIC: 0.23,
        ReferralSource.HEALTHCARE_PROFESSIONAL: 0.25,
        ReferralSource.INTERNAL_TRANSFER: 0.10,
    }


def _default_service_line_mix() -> dict[ServiceLine, float]:
    return {
        ServiceLine.CARDIOLOGY: 0.20,
        ServiceLine.DERMATOLOGY: 0.20,
        ServiceLine.MUSCULOSKELETAL: 0.25,
        ServiceLine.NEUROLOGY: 0.20,
        ServiceLine.RESPIRATORY: 0.15,
    }


def _default_team_allocation() -> dict[ServiceLine, tuple[str, ...]]:
    return {
        ServiceLine.CARDIOLOGY: ("TEAM-CARD-01", "TEAM-CARD-02"),
        ServiceLine.DERMATOLOGY: ("TEAM-DERM-01", "TEAM-DERM-02"),
        ServiceLine.MUSCULOSKELETAL: ("TEAM-MSK-01", "TEAM-MSK-02", "TEAM-MSK-03"),
        ServiceLine.NEUROLOGY: ("TEAM-NEUR-01", "TEAM-NEUR-02"),
        ServiceLine.RESPIRATORY: ("TEAM-RESP-01", "TEAM-RESP-02"),
    }


class OperationalParameters(ConfigModel):
    """Small set of timing, calendar, mix, and allocation controls."""

    completeness_check_delay: DurationRange = DurationRange(minimum=0.5, maximum=10)
    missing_information_response_delay: DurationRange = DurationRange(minimum=8, maximum=72)
    categorisation_duration: DurationRange = DurationRange(minimum=0.25, maximum=3)
    team_assignment_delay: DurationRange = DurationRange(minimum=1, maximum=12)
    appointment_booking_delay: DurationRange = DurationRange(minimum=8, maximum=72)
    notification_delay: DurationRange = DurationRange(minimum=0.1, maximum=2)
    reassignment_delay: DurationRange = DurationRange(minimum=3, maximum=16)
    failed_scheduling_delay: DurationRange = DurationRange(minimum=8, maximum=36)
    working_hour_start: int = Field(default=8, ge=0, le=23)
    working_hour_end: int = Field(default=18, ge=1, le=24)
    skip_weekends: bool = True
    source_system_mix: dict[SourceSystem, float] = Field(default_factory=_default_source_system_mix)
    referral_source_mix: dict[ReferralSource, float] = Field(
        default_factory=_default_referral_source_mix
    )
    service_line_mix: dict[ServiceLine, float] = Field(default_factory=_default_service_line_mix)
    admin_actor_ids: tuple[str, ...] = ("ADMIN-001", "ADMIN-002", "ADMIN-003", "ADMIN-004")
    scheduling_actor_ids: tuple[str, ...] = ("SCHED-001", "SCHED-002", "SCHED-003")
    team_allocation: dict[ServiceLine, tuple[str, ...]] = Field(
        default_factory=_default_team_allocation
    )

    @model_validator(mode="after")
    def validate_operating_model(self) -> Self:
        if self.working_hour_end <= self.working_hour_start:
            raise ValueError("working_hour_end must be later than working_hour_start")
        for label, mix in (
            ("source_system_mix", self.source_system_mix),
            ("referral_source_mix", self.referral_source_mix),
            ("service_line_mix", self.service_line_mix),
        ):
            if not mix or any(weight < 0 for weight in mix.values()):
                raise ValueError(f"{label} must contain non-negative weights")
            if not isclose(sum(mix.values()), 1.0, abs_tol=1e-9):
                raise ValueError(f"{label} weights must sum to 1.0")
        if not self.admin_actor_ids or not self.scheduling_actor_ids:
            raise ValueError("actor allocations cannot be empty")
        missing_teams = set(self.service_line_mix) - set(self.team_allocation)
        if missing_teams:
            raise ValueError(f"team allocation missing service lines: {sorted(missing_teams)}")
        return self


class BottleneckParameters(ConfigModel):
    """Segments and effect sizes for known future-analysis signals."""

    incomplete_referral_source: ReferralSource = ReferralSource.GP_PRACTICE
    incomplete_rate_multiplier: float = Field(default=2.5, ge=1)
    congested_service_line: ServiceLine = ServiceLine.NEUROLOGY
    assignment_delay_multiplier: float = Field(default=3.0, ge=1)
    scheduling_friction_service_line: ServiceLine = ServiceLine.RESPIRATORY
    scheduling_failure_multiplier: float = Field(default=3.0, ge=1)
    handoff_service_line: ServiceLine = ServiceLine.DERMATOLOGY
    reassignment_rate_multiplier: float = Field(default=3.0, ge=1)
    reassignment_delay_multiplier: float = Field(default=1.75, ge=1)


class GenerationConfig(ConfigModel):
    """Complete effective configuration for one logical generation run."""

    seed: int = Field(default=42, ge=0)
    case_count: int = Field(default=1_000, ge=1, le=100_000)
    period_start: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    operating_days: int = Field(default=180, ge=1, le=730)
    source_timezone: str = "Europe/London"
    output_mode: OutputMode = OutputMode.MEMORY
    persist: bool = False
    batch_size: int = Field(default=500, ge=1, le=10_000)
    generation_run_id: RunIdentifier | None = None
    outcomes: OutcomeRates = OutcomeRates()
    deviations: DeviationRates = DeviationRates()
    operations: OperationalParameters = OperationalParameters()
    bottlenecks: BottleneckParameters = BottleneckParameters()

    @field_validator("period_start")
    @classmethod
    def validate_period_start(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("period_start must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("source_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown IANA timezone: {value}") from error
        return value
