"""WorkflowTwin-owned process reconstruction and conformance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from workflowtwin.analytics.models import AnalysisInput, CaseMetrics

if TYPE_CHECKING:
    from workflowtwin.analytics.models import BaselineAnalysis


class ProcessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EventLogRecord(ProcessModel):
    case_id: UUID
    event_id: UUID
    activity: str
    event_at: datetime
    ingested_at: datetime
    lifecycle_status: str
    actor_type: str
    actor_identifier: str | None
    team_identifier: str | None
    source_system: str
    referral_source: str
    service_line: str
    channel: str
    requires_manual_work: bool
    reason_code: str | None
    is_synthetic: bool


class ProcessTrace(ProcessModel):
    case_id: UUID
    events: tuple[EventLogRecord, ...]
    warnings: tuple[str, ...] = ()

    @property
    def activities(self) -> tuple[str, ...]:
        return tuple(event.activity for event in self.events)


class ProcessLogQuality(ProcessModel):
    cases_received: int
    traces_included: int
    traces_excluded: int
    events_received: int
    events_included: int
    duplicate_events_excluded: int
    orphan_event_count: int
    empty_case_count: int
    unsupported_schema_cases: int
    unsupported_mapping_count: int
    identical_timestamp_cases: int
    out_of_order_ingestion_cases: int
    warnings: tuple[str, ...]


class ProcessLog(ProcessModel):
    activity_mapping_version: str
    traces: tuple[ProcessTrace, ...]
    quality: ProcessLogQuality


class NumericSummary(ProcessModel):
    count: int
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    percentiles: dict[str, float]


class ActivityStatistics(ProcessModel):
    activity: str
    frequency: int
    distinct_case_count: int
    manual_work_rate: float
    average_case_position: float
    repeated_case_count: int


class TransitionStatistics(ProcessModel):
    transition_id: str
    source_activity: str
    target_activity: str
    frequency: int
    distinct_case_count: int
    eligible_case_percentage: float
    elapsed_hours: NumericSummary
    business_hours: NumericSummary
    manual_touch_rate: float
    handoff_rate: float
    rework_rate: float
    terminal_transition: bool
    supporting_case_ids: tuple[UUID, ...]
    warnings: tuple[str, ...] = ()


class LoopStatistics(ProcessModel):
    loop_id: str
    loop_type: str
    activities: tuple[str, ...]
    occurrence_count: int
    distinct_case_count: int
    median_elapsed_hours: float | None
    supporting_case_ids: tuple[UUID, ...]


class VariantClassification(StrEnum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"


class VariantConformanceSummary(ProcessModel):
    strict_mean_fitness: float | None
    governed_mean_fitness: float | None
    strict_fully_conforming_rate: float | None
    governed_fully_conforming_rate: float | None


class ProcessVariant(ProcessModel):
    variant_id: str
    activities: tuple[str, ...]
    case_count: int
    case_percentage: float
    outcome_distribution: dict[str, int]
    duration_hours: NumericSummary
    mean_manual_touches: float | None
    mean_handoffs: float | None
    mean_rework_count: float | None
    first_pass_completeness_rate: float | None
    service_line_distribution: dict[str, int]
    referral_source_distribution: dict[str, int]
    representative_case_ids: tuple[UUID, ...]
    conformance: VariantConformanceSummary | None
    classification: VariantClassification
    markers: tuple[str, ...]


class ProcessComplexity(ProcessModel):
    distinct_activity_count: int
    distinct_transition_count: int
    distinct_variant_count: int
    top_1_variant_coverage: float
    top_5_variant_coverage: float
    top_10_variant_coverage: float
    long_tail_variant_count: int
    mean_activities_per_case: float
    median_activities_per_case: float
    maximum_activities_per_case: int
    loop_case_rate: float
    rework_case_rate: float
    handoff_case_rate: float
    terminal_path_diversity: int
    variant_entropy_bits: float


class ProcessDiscoveryResult(ProcessModel):
    algorithm: str
    noise_threshold: float
    discovered: bool
    process_tree: str | None
    petri_net_place_count: int
    petri_net_transition_count: int
    pm4py_dfg_matches_canonical: bool
    warnings: tuple[str, ...]


class DeviationCategory(StrEnum):
    UNEXPECTED_ACTIVITY = "unexpected_activity"
    MISSING_ACTIVITY = "missing_activity"
    ACTIVITY_REPEATED = "activity_repeated"
    UNEXPECTED_ORDER = "unexpected_order"
    EARLY_TERMINATION = "early_termination"
    MISSING_TERMINAL = "missing_terminal_event"
    UNEXPECTED_TERMINAL = "unexpected_terminal_event"
    EXCESSIVE_LOOP = "excessive_loop"
    UNEXPECTED_REASSIGNMENT = "unexpected_reassignment"
    UNEXPECTED_RECATEGORISATION = "unexpected_recategorisation"
    SCHEDULING_RETRY = "scheduling_retry"
    UNSUPPORTED_ACTIVITY = "unsupported_activity"
    CONFORMANCE_UNAVAILABLE = "conformance_unavailable"


class Deviation(ProcessModel):
    deviation_id: str
    category: DeviationCategory
    activity: str | None
    position: int | None
    description: str
    source_event_ids: tuple[UUID, ...]


class ConformanceStatus(StrEnum):
    FULLY_CONFORMING = "fully_conforming"
    PARTIALLY_CONFORMING = "partially_conforming"
    NON_CONFORMING = "non_conforming"
    UNAVAILABLE = "unavailable"


class TraceConformanceResult(ProcessModel):
    case_id: UUID
    reference_model: str
    fitness: float | None
    status: ConformanceStatus
    alignment_cost: float | None
    observed_sequence: tuple[str, ...]
    deviations: tuple[Deviation, ...]
    missing_expected_activities: tuple[str, ...]
    unexpected_observed_activities: tuple[str, ...]
    warnings: tuple[str, ...]
    source_event_ids: tuple[UUID, ...]


class CohortConformance(ProcessModel):
    dimension: str
    value: str
    case_count: int
    available_count: int
    mean_fitness: float | None
    fully_conforming_rate: float | None


class ConformanceSummary(ProcessModel):
    reference_model: str
    case_count: int
    available_count: int
    unavailable_count: int
    average_fitness: float | None
    median_fitness: float | None
    fully_conforming_rate: float | None
    partially_conforming_rate: float | None
    non_conforming_rate: float | None
    timeout_count: int
    failure_count: int
    by_terminal_outcome: tuple[CohortConformance, ...]
    by_referral_source: tuple[CohortConformance, ...]
    by_service_line: tuple[CohortConformance, ...]
    deviation_counts: dict[str, int]


class ReferenceProcess(ProcessModel):
    reference_id: str
    version: str
    description: str
    activities: tuple[str, ...]
    terminal_activities: tuple[str, ...]


class Materiality(StrEnum):
    SMALL = "small"
    MATERIAL = "material"
    STRONG = "strong"


class ProcessBottleneckCandidate(ProcessModel):
    candidate_id: str
    candidate_type: str
    subject: str
    cohort_dimension: str | None
    cohort_value: str | None
    frequency: int
    case_count: int
    elapsed_hours: NumericSummary
    comparison_value: float | None
    absolute_difference: float | None
    relative_difference: float | None
    manual_touch_rate: float | None
    handoff_rate: float | None
    conformance_context: str
    supporting_case_ids: tuple[UUID, ...]
    materiality: Materiality
    warnings: tuple[str, ...]


class BaselineReconciliation(ProcessModel):
    baseline_finding_id: str
    supporting_process_ids: tuple[str, ...]
    supports_finding: bool
    contradicts_finding: bool
    evidence: str
    sample_size: int
    caveats: tuple[str, ...]


class ProcessBottleneckEvaluation(ProcessModel):
    bottleneck: str
    detected: bool
    evidence_ids: tuple[str, ...]
    expected_direction: str
    observed_direction: str | None
    sample_size: int
    materiality_met: bool


class ProcessGroundTruthEvaluation(ProcessModel):
    status: str
    bottlenecks: tuple[ProcessBottleneckEvaluation, ...]
    detected_count: int
    planted_count: int
    false_negatives: tuple[str, ...]
    unexpected_candidate_ids: tuple[str, ...]
    notes: tuple[str, ...]


class ProcessGraphNode(ProcessModel):
    node_id: str
    activity: str
    frequency: int
    distinct_case_count: int
    is_start: bool
    is_terminal: bool
    manual_work_rate: float
    average_case_position: float
    associated_rework_count: int
    conformance_deviation_count: int


class ProcessGraphEdge(ProcessModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    frequency: int
    distinct_case_count: int
    median_transition_delay_hours: float | None
    percentiles_hours: dict[str, float]
    median_business_delay_hours: float | None
    handoff_rate: float
    rework_rate: float
    conformance_deviation_rate: float
    bottleneck_materiality: str | None


class VariantGraph(ProcessModel):
    variant_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    case_count: int
    median_duration_hours: float | None
    dominant_outcome: str | None
    strict_fitness: float | None
    governed_fitness: float | None
    bottleneck_markers: tuple[str, ...]


class ProcessGraphData(ProcessModel):
    nodes: tuple[ProcessGraphNode, ...]
    edges: tuple[ProcessGraphEdge, ...]
    variants: tuple[VariantGraph, ...]


class ProcessMiningAnalysis(ProcessModel):
    analysis_version: str
    analysis_id: str
    source_dataset_fingerprint: str
    baseline_analysis_fingerprint: str | None
    generation_run_id: str | None
    activity_mapping_version: str
    reference_model_versions: tuple[str, ...]
    configuration: dict[str, JsonValue]
    analysed_at: datetime
    case_count: int
    event_count: int
    log_quality: ProcessLogQuality
    activity_statistics: tuple[ActivityStatistics, ...]
    transition_statistics: tuple[TransitionStatistics, ...]
    start_activity_counts: dict[str, int]
    end_activity_counts: dict[str, int]
    loops: tuple[LoopStatistics, ...]
    variants: tuple[ProcessVariant, ...]
    complexity: ProcessComplexity
    discovery: ProcessDiscoveryResult
    strict_conformance: ConformanceSummary | None
    governed_conformance: ConformanceSummary | None
    deviation_summary: dict[str, int]
    bottleneck_candidates: tuple[ProcessBottleneckCandidate, ...]
    baseline_reconciliation: tuple[BaselineReconciliation, ...]
    ground_truth_evaluation: ProcessGroundTruthEvaluation
    graph_data: ProcessGraphData
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]
    process_analysis_fingerprint: str
    fictional_data_confirmation: str


class CaseProcessResult(ProcessModel):
    case_id: UUID
    variant_id: str
    strict_conformance: TraceConformanceResult | None
    governed_conformance: TraceConformanceResult | None
    transition_ids: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProcessAnalysisInput:
    operational: AnalysisInput
    baseline: BaselineAnalysis | None = None


@dataclass(frozen=True, slots=True)
class ProcessMiningBundle:
    analysis: ProcessMiningAnalysis
    case_results: tuple[CaseProcessResult, ...]
    process_log: ProcessLog
    case_metrics: tuple[CaseMetrics, ...]
    visualisation_warnings: tuple[str, ...] = ()
