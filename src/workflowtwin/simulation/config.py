"""Validated configuration and scenario presets for counterfactual simulation."""

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

SimulationIdentifier = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$", max_length=64)
]


class ScenarioId(StrEnum):
    CONSERVATIVE = "conservative"
    CENTRAL = "central"
    OPTIMISTIC = "optimistic"
    ADVERSE = "adverse"


class ScenarioParameters(BaseModel):
    """Explicit assumptions for one fictional counterfactual scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rollout_percentage: float = Field(ge=0, le=1)
    effectiveness: float = Field(ge=0, le=1)
    false_positive_rate: float = Field(ge=0, le=1)
    false_negative_rate: float = Field(ge=0, le=1)
    human_review_acceptance_rate: float = Field(ge=0, le=1)
    human_review_timeout_rate: float = Field(ge=0, le=1)
    human_review_turnaround_hours: tuple[float, float]
    system_processing_delay_hours: tuple[float, float]
    manual_fallback_rate: float = Field(ge=0, le=1)
    intervention_failure_rate: float = Field(ge=0, le=1)
    rollback_rate: float = Field(ge=0, le=1)
    rollback_recovery_delay_hours: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        for name, values in (
            ("human_review_turnaround_hours", self.human_review_turnaround_hours),
            ("system_processing_delay_hours", self.system_processing_delay_hours),
        ):
            if values[0] < 0 or values[1] < values[0]:
                raise ValueError(f"{name} must be a non-negative ordered range")
        if self.false_negative_rate > 1 - self.effectiveness + 1e-9:
            raise ValueError("false_negative_rate cannot exceed one minus effectiveness")
        return self


SCENARIOS: dict[ScenarioId, ScenarioParameters] = {
    ScenarioId.CONSERVATIVE: ScenarioParameters(
        rollout_percentage=0.50,
        effectiveness=0.55,
        false_positive_rate=0.10,
        false_negative_rate=0.35,
        human_review_acceptance_rate=0.72,
        human_review_timeout_rate=0.10,
        human_review_turnaround_hours=(1.0, 6.0),
        system_processing_delay_hours=(0.10, 0.50),
        manual_fallback_rate=0.15,
        intervention_failure_rate=0.08,
        rollback_rate=0.05,
        rollback_recovery_delay_hours=3.0,
    ),
    ScenarioId.CENTRAL: ScenarioParameters(
        rollout_percentage=0.70,
        effectiveness=0.70,
        false_positive_rate=0.06,
        false_negative_rate=0.22,
        human_review_acceptance_rate=0.82,
        human_review_timeout_rate=0.06,
        human_review_turnaround_hours=(0.5, 3.0),
        system_processing_delay_hours=(0.05, 0.25),
        manual_fallback_rate=0.10,
        intervention_failure_rate=0.04,
        rollback_rate=0.03,
        rollback_recovery_delay_hours=2.0,
    ),
    ScenarioId.OPTIMISTIC: ScenarioParameters(
        rollout_percentage=0.85,
        effectiveness=0.82,
        false_positive_rate=0.03,
        false_negative_rate=0.12,
        human_review_acceptance_rate=0.90,
        human_review_timeout_rate=0.03,
        human_review_turnaround_hours=(0.25, 1.5),
        system_processing_delay_hours=(0.03, 0.15),
        manual_fallback_rate=0.06,
        intervention_failure_rate=0.02,
        rollback_rate=0.01,
        rollback_recovery_delay_hours=1.0,
    ),
    ScenarioId.ADVERSE: ScenarioParameters(
        rollout_percentage=0.70,
        effectiveness=0.45,
        false_positive_rate=0.22,
        false_negative_rate=0.40,
        human_review_acceptance_rate=0.62,
        human_review_timeout_rate=0.20,
        human_review_turnaround_hours=(3.0, 12.0),
        system_processing_delay_hours=(0.25, 1.0),
        manual_fallback_rate=0.30,
        intervention_failure_rate=0.15,
        rollback_rate=0.10,
        rollback_recovery_delay_hours=8.0,
    ),
}


class SimulationConfig(BaseModel):
    """Source identity, policy controls, assumptions, and output choices."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    simulation_id: SimulationIdentifier = "northstar-completeness-simulation"
    simulation_version: str = "1.0.0"
    scenario_id: ScenarioId = ScenarioId.CENTRAL
    selected_opportunity_id: str
    source_dataset_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    baseline_analysis_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    process_analysis_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    opportunity_analysis_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    generation_run_id: str | None = None
    intervention_definition_version: str = "1.0.0"
    policy_version: str = "northstar-completeness-policy-v1"
    simulation_seed: int = 42
    period_start: datetime | None = None
    period_end: datetime | None = None
    maximum_affected_case_count: int = Field(default=10_000, ge=1, le=100_000)
    parameters: ScenarioParameters
    administrative_cost_per_hour_gbp: float = Field(default=24.0, gt=0)
    manual_touch_minutes_proxy: float = Field(default=5.0, gt=0)
    working_timezone: str = "Europe/London"
    working_hour_start: int = Field(default=8, ge=0, le=23)
    working_hour_end: int = Field(default=18, ge=1, le=24)
    skip_weekends: bool = True
    analysis_output: Path | None = None
    report_output: Path | None = None
    comparison_output: Path | None = None
    case_output: Path | None = None
    overwrite: bool = False

    @field_validator("period_start", "period_end")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("simulation timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("working_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown IANA timezone: {value}") from error
        return value

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.period_start and self.period_end and self.period_end <= self.period_start:
            raise ValueError("period_end must be later than period_start")
        if self.working_hour_end <= self.working_hour_start:
            raise ValueError("working_hour_end must be later than working_hour_start")
        if self.intervention_definition_version != "1.0.0":
            raise ValueError("unsupported intervention definition version")
        if self.policy_version != "northstar-completeness-policy-v1":
            raise ValueError("unsupported intervention policy version")
        return self


def config_for_scenario(
    *,
    scenario_id: ScenarioId,
    selected_opportunity_id: str,
    source_dataset_fingerprint: str,
    baseline_analysis_fingerprint: str,
    process_analysis_fingerprint: str,
    opportunity_analysis_fingerprint: str,
    generation_run_id: str | None,
    simulation_seed: int = 42,
    parameters: ScenarioParameters | None = None,
    **overrides: object,
) -> SimulationConfig:
    """Create a scenario config while keeping every assumption serializable."""
    return SimulationConfig.model_validate(
        {
            "scenario_id": scenario_id,
            "selected_opportunity_id": selected_opportunity_id,
            "source_dataset_fingerprint": source_dataset_fingerprint,
            "baseline_analysis_fingerprint": baseline_analysis_fingerprint,
            "process_analysis_fingerprint": process_analysis_fingerprint,
            "opportunity_analysis_fingerprint": opportunity_analysis_fingerprint,
            "generation_run_id": generation_run_id,
            "simulation_seed": simulation_seed,
            "parameters": parameters or SCENARIOS[scenario_id],
            **overrides,
        }
    )
