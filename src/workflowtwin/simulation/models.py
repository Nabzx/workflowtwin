"""WorkflowTwin-owned intervention and counterfactual simulation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, JsonValue

from workflowtwin.analytics.models import AnalysisInput, BaselineAnalysis, MetricStatus
from workflowtwin.domain.referrals.models import ReferralEvent
from workflowtwin.opportunities.models import OpportunityAnalysis, OpportunityCandidate
from workflowtwin.process_mining.models import ProcessMiningAnalysis
from workflowtwin.synthetic.models import GenerationGroundTruth, GenerationManifest


class SimulationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InterventionAction(StrEnum):
    OBSERVE_STRUCTURED_FIELDS = "observe_structured_administrative_fields"
    RECOMMEND_COMPLETENESS_REVIEW = "recommend_completeness_review"
    REQUEST_HUMAN_APPROVAL = "request_human_approval"
    RECORD_APPROVED_VALIDATION = "record_approved_structured_validation"
    FALLBACK_TO_MANUAL = "fallback_to_manual_workflow"
    ROLLBACK = "rollback_counterfactual_action"


class PolicyDecisionStatus(StrEnum):
    NOT_ELIGIBLE = "not_eligible"
    OBSERVE_ONLY = "observe_only"
    GENERATE_RECOMMENDATION = "generate_recommendation"
    REQUEST_HUMAN_APPROVAL = "request_human_approval"
    APPROVED_SIMULATED_ACTION = "approved_simulated_action"
    REJECTED_BY_REVIEWER = "rejected_by_reviewer"
    FALLBACK_TO_MANUAL = "fallback_to_manual_process"
    BLOCKED_MISSING_INFORMATION = "blocked_by_missing_information"
    BLOCKED_POLICY = "blocked_by_policy"
    SIMULATION_FAILURE = "simulation_failure"
    ROLLED_BACK = "rolled_back"


class EventChangeType(StrEnum):
    RETAINED = "event_retained_unchanged"
    REPLACED = "event_replaced_in_counterfactual_view"
    TIMESTAMP_SHIFTED = "event_timestamp_shifted"
    MANUAL_MARKER_CHANGED = "manual_marker_changed"
    ACTOR_TYPE_CHANGED = "actor_type_changed"
    ROUTED_TO_HUMAN_APPROVAL = "action_routed_to_human_approval"
    FAILURE_RECORDED = "simulated_failure_recorded"
    FALLBACK_RECORDED = "fallback_recorded"
    ROLLBACK_RECORDED = "rollback_recorded"


class EffectClassification(StrEnum):
    INTENDED_DIRECT = "intended_direct_effect"
    SECONDARY = "secondary_operational_effect"
    CONTROL_OVERHEAD = "control_overhead"
    ADVERSE = "adverse_effect"
    UNCHANGED = "unchanged"


class PrototypeDecisionStatus(StrEnum):
    PROCEED_SHADOW = "proceed_to_shadow_mode_prototype"
    PROCEED_WITH_CONTROLS = "proceed_only_with_additional_controls"
    REVISE = "revise_intervention_design"
    GATHER_EVIDENCE = "gather_more_evidence"
    DO_NOT_PROCEED = "do_not_proceed"


class InterventionDefinition(SimulationModel):
    intervention_id: str
    intervention_version: str
    definition_fingerprint: str
    source_opportunity_id: str
    opportunity_archetype: str
    operational_problem: str
    affected_cohort_dimension: str
    affected_cohort_value: str
    workflow_stage: str
    trigger_conditions: tuple[str, ...]
    required_structured_inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    allowed_actions: tuple[InterventionAction, ...]
    prohibited_actions: tuple[str, ...]
    human_review_required: bool
    required_reviewer_role: str
    escalation_conditions: tuple[str, ...]
    audit_requirements: tuple[str, ...]
    fallback_behaviour: str
    rollback_behaviour: str
    evaluation_metrics: tuple[str, ...]
    known_failure_modes: tuple[str, ...]
    safety_constraints: tuple[str, ...]
    assumptions: tuple[str, ...]


class CaseEligibility(SimulationModel):
    case_id: UUID
    eligible: bool
    reason_codes: tuple[str, ...]
    trigger_event_ids: tuple[UUID, ...]
    warnings: tuple[str, ...] = ()


class InterventionDecision(SimulationModel):
    case_id: UUID
    policy_version: str
    status: PolicyDecisionStatus
    reason_codes: tuple[str, ...]
    relevant_event_ids: tuple[UUID, ...]
    triggering_evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    required_reviewer_role: str | None
    simulated_action: InterventionAction | None
    review_turnaround_hours: float | None
    manual_touch_overhead: float
    warnings: tuple[str, ...]


class EventChange(SimulationModel):
    change_id: str
    simulation_run_id: str
    intervention_id: str
    case_id: UUID
    source_event_id: UUID | None
    counterfactual_event_id: UUID | None
    change_types: tuple[EventChangeType, ...]
    original_event: ReferralEvent | None
    counterfactual_event: ReferralEvent | None
    causal_simulation_rule: str
    event_time_adjustment_hours: float | None
    ingestion_time_treatment: str
    human_review_action: str | None
    warnings: tuple[str, ...]
    provenance: tuple[str, ...]


class CaseSimulationResult(SimulationModel):
    case_id: UUID
    eligibility: CaseEligibility
    decision: InterventionDecision
    hidden_simulation_truth: str
    detector_outcome: str
    event_changes: tuple[EventChange, ...]


class SimulationQualityReport(SimulationModel):
    is_valid: bool
    source_events_unchanged: bool
    counterfactual_event_count: int
    unique_event_identifiers: bool
    orphan_event_count: int
    timezone_issue_count: int
    event_order_issue_count: int
    forbidden_metadata_count: int
    provenance_issue_count: int
    policy_change_mismatch_count: int
    expected_failure_count: int
    findings: tuple[str, ...]
    warnings: tuple[str, ...]


class SimulationManifest(SimulationModel):
    simulation_version: str
    simulation_id: str
    simulation_run_id: str
    scenario_id: str
    source_dataset_fingerprint: str
    baseline_analysis_fingerprint: str
    process_analysis_fingerprint: str
    opportunity_analysis_fingerprint: str
    selected_opportunity_id: str
    intervention_id: str
    intervention_version: str
    policy_version: str
    seed: int
    configuration: dict[str, JsonValue]
    source_case_count: int
    source_event_count: int
    eligible_case_count: int
    excluded_case_count: int
    affected_case_count: int
    observe_only_count: int
    review_required_count: int
    approved_action_count: int
    rejected_action_count: int
    intervention_failure_count: int
    fallback_count: int
    rollback_count: int
    counterfactual_case_count: int
    counterfactual_event_count: int
    change_type_counts: dict[str, int]
    configured_rates: dict[str, float]
    realised_rates: dict[str, float | None]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    counterfactual_dataset_fingerprint: str
    fictional_counterfactual_declaration: str


class MetricComparison(SimulationModel):
    metric_name: str
    baseline_value: float | None
    simulated_value: float | None
    absolute_difference: float | None
    relative_difference: float | None
    unit: str
    denominator: int | None
    cohort_dimension: str
    cohort_value: str
    status: MetricStatus
    effect_classification: EffectClassification
    interpretation: str
    warnings: tuple[str, ...]


class ProcessComparison(SimulationModel):
    metric_name: str
    baseline_value: float | int | None
    simulated_value: float | int | None
    absolute_difference: float | None
    interpretation: str
    warnings: tuple[str, ...]


class BurdenComparison(SimulationModel):
    baseline_manual_touch_hours: float
    simulated_workflow_touch_hours: float
    review_overhead_hours: float
    fallback_overhead_hours: float
    failure_recovery_hours: float
    simulated_operating_burden_hours: float
    gross_simulated_difference_hours: float
    net_simulated_difference_hours: float
    addressable_upper_bound_hours: float
    upper_bound_proportion_modelled: float | None
    baseline_associated_cost_gbp: float
    simulated_associated_cost_gbp: float
    simulated_operating_cost_gbp: float
    simulated_net_cost_difference_gbp: float
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]


class AnalysisSummary(SimulationModel):
    analysis_fingerprint: str
    case_count: int
    event_count: int
    cohort_dimension: str
    cohort_value: str
    metrics: dict[str, float | int | None]
    warning_count: int


class ProcessSummary(SimulationModel):
    process_analysis_fingerprint: str
    activity_count: int
    transition_count: int
    variant_count: int
    governed_fully_conforming_rate: float | None
    strict_fully_conforming_rate: float | None
    bottleneck_candidate_count: int
    complexity: dict[str, float | int | None]


class ScenarioResult(SimulationModel):
    scenario_id: str
    scenario_fingerprint: str
    manifest: SimulationManifest
    quality: SimulationQualityReport
    case_results: tuple[CaseSimulationResult, ...]
    baseline_summary: AnalysisSummary
    counterfactual_summary: AnalysisSummary
    baseline_process_summary: ProcessSummary
    counterfactual_process_summary: ProcessSummary
    metric_comparisons: tuple[MetricComparison, ...]
    process_comparisons: tuple[ProcessComparison, ...]
    burden_comparison: BurdenComparison
    direct_effects: tuple[str, ...]
    secondary_effects: tuple[str, ...]
    control_overhead: tuple[str, ...]
    adverse_effects: tuple[str, ...]
    counterfactual_baseline_fingerprint: str
    counterfactual_process_fingerprint: str


class SensitivityResult(SimulationModel):
    parameter: str
    baseline_value: float
    tested_value: float
    target_metric_difference: float | None
    net_burden_difference_hours: float
    control_overhead_hours: float
    conclusion_changed: bool
    scenario_fingerprint: str


class ThresholdResult(SimulationModel):
    parameter: str
    modelled_boundary: float | None
    tested_values: tuple[float, ...]
    net_burden_differences: tuple[float, ...]
    interpretation: str
    warnings: tuple[str, ...]


class ShadowModeRequirement(SimulationModel):
    category: str
    requirement: str


class PrototypeDecision(SimulationModel):
    status: PrototypeDecisionStatus
    criteria: dict[str, bool]
    rationale: tuple[str, ...]
    required_additional_controls: tuple[str, ...]
    tie_breaker: str
    limitations: tuple[str, ...]


class SimulationBenchmarkEvaluation(SimulationModel):
    checks: dict[str, bool]
    passed_count: int
    check_count: int
    notes: tuple[str, ...]


class SimulationGraphData(SimulationModel):
    metric_comparison: tuple[dict[str, JsonValue], ...]
    process_comparison: tuple[dict[str, JsonValue], ...]
    scenario_comparison: tuple[dict[str, JsonValue], ...]
    sensitivity: tuple[dict[str, JsonValue], ...]


class SimulationAnalysis(SimulationModel):
    simulation_version: str
    simulation_id: str
    analysed_at: datetime
    selected_opportunity: OpportunityCandidate
    intervention_definition: InterventionDefinition
    policy_version: str
    scenario_result: ScenarioResult
    sensitivity_results: tuple[SensitivityResult, ...]
    threshold_results: tuple[ThresholdResult, ...]
    decision: PrototypeDecision
    shadow_mode_requirements: tuple[ShadowModeRequirement, ...]
    benchmark_evaluation: SimulationBenchmarkEvaluation
    graph_data: SimulationGraphData
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    warnings: tuple[str, ...]
    simulation_analysis_fingerprint: str
    fictional_counterfactual_declaration: str


@dataclass(frozen=True, slots=True)
class SimulationInput:
    source: AnalysisInput
    baseline: BaselineAnalysis
    process: ProcessMiningAnalysis
    opportunities: OpportunityAnalysis
    manifest: GenerationManifest
    ground_truth: GenerationGroundTruth | None = None


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    operational: AnalysisInput
    case_results: tuple[CaseSimulationResult, ...]
    quality: SimulationQualityReport
    manifest: SimulationManifest
