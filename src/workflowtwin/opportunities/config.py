"""Validated configuration for deterministic opportunity identification."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

OpportunityAnalysisIdentifier = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$", max_length=64)
]


class AnnualisationPolicy(StrEnum):
    NONE = "none"
    REPORTING_PERIOD = "reporting_period"


class OpportunityConfig(BaseModel):
    """Scoring choices and visible burden assumptions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: OpportunityAnalysisIdentifier = "northstar-opportunities-v1"
    expected_baseline_version: str = "1.0.0"
    expected_process_version: str = "1.0.0"
    expected_event_schema_version: int = Field(default=1, ge=1)
    expected_activity_map_version: str = "northstar-activity-map-v1"
    expected_reference_models: tuple[str, ...] = (
        "northstar-strict-v1",
        "northstar-governed-v1",
    )
    expected_research_pack_version: str = "northstar-research-v1"
    minimum_sample_size: int = Field(default=20, ge=2)
    minimum_quantitative_evidence: int = Field(default=2, ge=1)
    administrative_cost_per_hour_gbp: float = Field(default=24.0, gt=0)
    manual_touch_minutes_proxy: float = Field(default=5.0, gt=0)
    annualisation_policy: AnnualisationPolicy = AnnualisationPolicy.NONE
    value_weight: float = Field(default=0.40, ge=0, le=1)
    readiness_weight: float = Field(default=0.25, ge=0, le=1)
    confidence_weight: float = Field(default=0.25, ge=0, le=1)
    risk_weight: float = Field(default=0.10, ge=0, le=1)
    prototype_priority_threshold: float = Field(default=55.0, ge=0, le=100)
    analysis_output: Path | None = None
    report_output: Path | None = None
    portfolio_output: Path | None = None
    evidence_output: Path | None = None
    overwrite: bool = False

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        if (
            abs(
                self.value_weight
                + self.readiness_weight
                + self.confidence_weight
                + self.risk_weight
                - 1.0
            )
            > 1e-9
        ):
            raise ValueError("opportunity scoring weights must sum to 1.0")
        return self
