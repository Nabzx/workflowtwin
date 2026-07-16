"""Ground truth, manifest, validation, and generated dataset contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from workflowtwin.domain.referrals.enums import ReferralStatus
from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent
from workflowtwin.synthetic.config import GenerationConfig


class SyntheticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BottleneckLabel(StrEnum):
    INCOMPLETE_REFERRALS = "incomplete_referrals"
    ASSIGNMENT_CONGESTION = "assignment_congestion"
    SCHEDULING_FRICTION = "scheduling_friction"
    HANDOFF_COST = "handoff_cost"


class DefectType(StrEnum):
    DUPLICATE_SOURCE_EVENT = "duplicate_source_event"
    DELAYED_INGESTION = "delayed_ingestion"
    OUT_OF_ORDER_INGESTION = "out_of_order_ingestion"
    MISSING_OPTIONAL_ACTOR = "missing_optional_actor"
    UNEXPECTED_CHANNEL = "unexpected_channel"
    SOURCE_IDENTIFIER_INCONSISTENCY = "source_identifier_inconsistency"
    SOURCE_RETRY = "source_retry"


class CaseGroundTruth(SyntheticModel):
    case_id: UUID
    intended_outcome: ReferralStatus
    intended_path: tuple[str, ...]
    bottlenecks: tuple[BottleneckLabel, ...]
    defects: tuple[DefectType, ...]
    has_rework: bool
    has_handoff: bool
    is_intentionally_stuck: bool


class EventGroundTruth(SyntheticModel):
    event_id: UUID
    defects: tuple[DefectType, ...]


class DuplicateSourceAttempt(SyntheticModel):
    attempted_event_id: UUID
    canonical_event_id: UUID
    source_system: str
    external_event_id: str
    defect: DefectType


class GenerationGroundTruth(SyntheticModel):
    run_id: str
    cases: tuple[CaseGroundTruth, ...]
    events: tuple[EventGroundTruth, ...]
    duplicate_attempts: tuple[DuplicateSourceAttempt, ...]


class GenerationManifest(SyntheticModel):
    generator_version: str
    schema_version: int
    random_seed: int
    generation_run_id: str
    configuration: dict[str, JsonValue]
    generated_case_count: int
    generated_event_count: int
    period_start: datetime
    period_end: datetime
    outcome_counts: dict[str, int]
    scenario_counts: dict[str, int]
    source_system_distribution: dict[str, int]
    service_line_distribution: dict[str, int]
    referral_source_distribution: dict[str, int]
    planted_bottlenecks: dict[str, int]
    configured_defect_rates: dict[str, float]
    realised_defect_counts: dict[str, int]
    realised_defect_rates: dict[str, float]
    expected_qualitative_findings: tuple[str, ...]
    dataset_fingerprint: str
    generated_at: datetime
    fictional_data_confirmation: str


class ValidationSeverity(StrEnum):
    INVALID = "invalid"
    UNUSUAL = "valid_but_unusual"
    EXPECTED_DEFECT = "expected_synthetic_defect"


class ValidationFinding(SyntheticModel):
    severity: ValidationSeverity
    code: str
    count: int
    message: str


class DatasetValidationReport(SyntheticModel):
    is_valid: bool
    case_count: int
    event_count: int
    orphan_event_count: int
    duplicate_event_id_count: int
    duplicate_external_event_count: int
    invalid_terminal_case_count: int
    cases_without_events: int
    event_time_regression_count: int
    timezone_issue_count: int
    schema_version_mismatch_count: int
    forbidden_metadata_count: int
    event_type_counts: dict[str, int]
    terminal_outcome_counts: dict[str, int]
    stuck_case_count: int
    delayed_ingestion_count: int
    out_of_order_ingestion_count: int
    findings: tuple[ValidationFinding, ...]


@dataclass(frozen=True, slots=True)
class GeneratedDataset:
    """One complete in-memory synthetic generation result."""

    config: GenerationConfig
    cases: tuple[ReferralCase, ...]
    events: tuple[ReferralEvent, ...]
    ground_truth: GenerationGroundTruth
    manifest: GenerationManifest
