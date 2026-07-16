"""Typed analytical results, findings, and artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent

if TYPE_CHECKING:
    from workflowtwin.synthetic.models import GenerationGroundTruth, GenerationManifest


class AnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MetricStatus(StrEnum):
    CALCULATED = "calculated"
    ESTIMATED = "estimated"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"
    EXCLUDED = "excluded"
    INVALID_INPUT = "invalid_input"


class MetricPrecision(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class MetricName(StrEnum):
    CASE_DURATION = "case_duration_hours"
    CYCLE_TIME = "cycle_time_hours"
    WAITING_TIME = "waiting_time_business_hours"
    PROCESSING_TIME = "processing_time_estimate_hours"
    MANUAL_TOUCHES = "manual_touches"
    HANDOFFS = "handoffs"
    REWORK_COUNT = "rework_count"
    FIRST_PASS_COMPLETE = "first_pass_complete"
    TIME_TO_FIRST_CHECK = "time_to_first_completeness_check_hours"
    TIME_TO_BOOKING = "time_to_appointment_booking_hours"
    ASSIGNMENT_WAIT = "assignment_wait_business_hours"
    FAILED_SCHEDULING = "failed_scheduling_attempts"
    REASSIGNMENTS = "reassignment_count"
    IS_STUCK = "is_stuck"
    MAX_INGESTION_DELAY = "max_ingestion_delay_hours"
    DELAYED_EVENTS = "delayed_event_count"
    OUT_OF_ORDER_INGESTION = "out_of_order_ingestion"


class MetricResult(AnalysisModel):
    name: MetricName
    value: float | int | bool | None
    unit: str
    status: MetricStatus
    precision: MetricPrecision
    source_event_ids: tuple[UUID, ...] = ()
    start_event_id: UUID | None = None
    end_event_id: UUID | None = None
    exclusion_reason: str | None = None
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    calculation_version: str = "1.0.0"


class CaseMetrics(AnalysisModel):
    case_id: UUID
    lifecycle_status: str
    referral_source: str
    service_line: str
    primary_source_system: str | None
    assigned_team: str | None
    metrics: dict[MetricName, MetricResult]
    timeline_warnings: tuple[str, ...]


class SummaryMetric(AnalysisModel):
    available_count: int
    excluded_count: int
    mean: float | None
    median: float | None
    percentiles: dict[str, float]


class RateMetric(AnalysisModel):
    numerator: int
    denominator: int
    value: float | None


class CohortMetrics(AnalysisModel):
    dimension: str
    value: str
    case_count: int
    completed_count: int
    cancellation_count: int
    rejection_count: int
    stuck_count: int
    rates: dict[str, RateMetric]
    summaries: dict[str, SummaryMetric]
    eligible_for_comparison: bool


class AnalysisQuality(AnalysisModel):
    cases_received: int
    cases_analysed: int
    cases_excluded_entirely: int
    unsupported_schema_cases: int
    orphan_event_count: int
    ambiguous_timeline_cases: int
    identical_timestamp_cases: int
    delayed_ingestion_cases: int
    out_of_order_ingestion_cases: int
    missing_required_event_counts: dict[str, int]
    metric_status_counts: dict[str, dict[str, int]]
    data_validation_warnings: tuple[str, ...]
    configuration_warnings: tuple[str, ...]


class Materiality(StrEnum):
    SMALL = "small"
    MATERIAL = "material"
    STRONG = "strong"


class BaselineFinding(AnalysisModel):
    finding_id: str
    finding_type: str
    cohort_dimension: str
    cohort_value: str
    comparison: str
    metric_name: str
    observed_value: float
    baseline_value: float
    absolute_difference: float
    relative_difference: float | None
    cohort_size: int
    baseline_size: int
    materiality: Materiality
    supporting_case_ids: tuple[UUID, ...]
    caveats: tuple[str, ...]
    minimum_cohort_size_met: bool


class EvaluationStatus(StrEnum):
    EVALUATED = "evaluated"
    NOT_EVALUATED = "not_evaluated"


class BottleneckEvaluation(AnalysisModel):
    bottleneck: str
    detected: bool
    finding_id: str | None
    expected_cohort: str
    expected_direction: str
    observed_direction: str | None
    materiality_met: bool


class GroundTruthEvaluation(AnalysisModel):
    status: EvaluationStatus
    bottlenecks: tuple[BottleneckEvaluation, ...]
    detected_count: int
    planted_count: int
    false_negatives: tuple[str, ...]
    unexpected_finding_ids: tuple[str, ...]
    notes: tuple[str, ...]


class BaselineAnalysis(AnalysisModel):
    analysis_version: str
    analysis_id: str
    configuration: dict[str, JsonValue]
    source_dataset_fingerprint: str
    generation_run_id: str | None
    event_schema_version: int
    analysed_at: datetime
    reporting_period_start: datetime | None
    reporting_period_end: datetime | None
    case_count: int
    event_count: int
    overall: CohortMetrics
    cohorts: tuple[CohortMetrics, ...]
    quality: AnalysisQuality
    findings: tuple[BaselineFinding, ...]
    ground_truth_evaluation: GroundTruthEvaluation
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    warnings: tuple[str, ...]
    analysis_fingerprint: str
    fictional_data_confirmation: str


@dataclass(frozen=True, slots=True)
class AnalysisInput:
    cases: tuple[ReferralCase, ...]
    events: tuple[ReferralEvent, ...]
    dataset_fingerprint: str
    generation_run_id: str | None = None
    manifest: GenerationManifest | None = None
    ground_truth: GenerationGroundTruth | None = None


@dataclass(frozen=True, slots=True)
class AnalysisBundle:
    baseline: BaselineAnalysis
    case_metrics: tuple[CaseMetrics, ...]
