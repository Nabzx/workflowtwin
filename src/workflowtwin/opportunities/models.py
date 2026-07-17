"""WorkflowTwin-owned opportunity, evidence, research, and portfolio contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, JsonValue

from workflowtwin.analytics.models import BaselineAnalysis
from workflowtwin.process_mining.models import ProcessMiningAnalysis
from workflowtwin.synthetic.models import GenerationGroundTruth, GenerationManifest


class OpportunityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceSourceType(StrEnum):
    BASELINE_FINDING = "baseline_finding"
    COHORT_METRIC = "cohort_metric"
    PROCESS_TRANSITION = "process_transition"
    PROCESS_VARIANT = "process_variant"
    PROCESS_CANDIDATE = "process_candidate"
    PROCESS_DEVIATION = "process_deviation"
    PROCESS_QUALITY = "process_quality"
    BASELINE_QUALITY = "baseline_quality"
    RESEARCH_OBSERVATION = "research_observation"
    MANIFEST_QUALITY = "manifest_quality"


class EvidenceDirection(StrEnum):
    ELEVATED = "elevated"
    LOWER = "lower"
    PRESENT = "present"
    MIXED = "mixed"
    NOT_APPLICABLE = "not_applicable"


class EvidenceConfidence(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class OpportunityArchetypeId(StrEnum):
    INTAKE_COMPLETENESS = "intake-completeness-validation"
    CLASSIFICATION_ASSISTANCE = "administrative-classification-assistance"
    ASSIGNMENT_ROUTING = "assignment-routing-assistance"
    SCHEDULING_COORDINATION = "scheduling-coordination-assistance"
    STUCK_CASE_MONITORING = "stuck-case-monitoring"
    DATA_QUALITY_MONITORING = "data-quality-ingestion-monitoring"
    HANDOFF_REDUCTION = "handoff-reduction"


class OversightClass(StrEnum):
    OBSERVE_ONLY = "observe_only"
    HUMAN_REVIEW = "human_review"
    HUMAN_APPROVAL = "human_approval"


class OpportunityArchetype(OpportunityModel):
    archetype_id: OpportunityArchetypeId
    version: str
    title: str
    operational_purpose: str
    applicable_evidence_types: tuple[EvidenceSourceType, ...]
    minimum_eligibility_conditions: tuple[str, ...]
    disqualifying_conditions: tuple[str, ...]
    likely_action_class: str
    oversight_class: OversightClass
    success_measures: tuple[str, ...]
    known_failure_modes: tuple[str, ...]
    safety_restrictions: tuple[str, ...]


class ResearchRole(StrEnum):
    REFERRAL_ADMINISTRATOR = "referral_administrator"
    SCHEDULING_COORDINATOR = "scheduling_coordinator"
    OPERATIONS_MANAGER = "operations_manager"
    SERVICE_LINE_COORDINATOR = "service_line_coordinator"
    DATA_INTEGRATION_LEAD = "data_integration_lead"
    COMPLIANCE_GOVERNANCE_LEAD = "compliance_governance_lead"


class ResearchMethod(StrEnum):
    SEMI_STRUCTURED_INTERVIEW = "semi_structured_interview"
    WORKFLOW_WALKTHROUGH = "workflow_walkthrough"


class ReportedFrequency(StrEnum):
    RARE = "rare"
    OCCASIONAL = "occasional"
    FREQUENT = "frequent"
    DAILY = "daily"
    UNKNOWN = "unknown"


class ReportedSeverity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ResearchObservation(OpportunityModel):
    observation_id: str
    reported_problem: str
    workflow_stage: str
    affected_role: ResearchRole
    frequency: ReportedFrequency
    severity: ReportedSeverity
    current_workaround: str
    desired_outcome: str
    adoption_constraints: tuple[str, ...]
    governance_constraints: tuple[str, ...]
    supporting_quote: str
    supported_archetypes: tuple[OpportunityArchetypeId, ...]
    cohort_dimension: str | None = None
    cohort_value: str | None = None
    contradicts: tuple[str, ...] = ()
    confidence_note: str


class ResearchSession(OpportunityModel):
    session_id: str
    participant_id: str
    role: ResearchRole
    department: str
    session_date: date
    method: ResearchMethod
    topics: tuple[str, ...]
    observations: tuple[ResearchObservation, ...]


class ResearchPack(OpportunityModel):
    pack_version: str
    title: str
    fictional_data_declaration: str
    sessions: tuple[ResearchSession, ...]


class EvidenceReference(OpportunityModel):
    evidence_id: str
    source_type: EvidenceSourceType
    source_artifact_fingerprint: str
    source_record_id: str
    metric_or_observation: str
    cohort_dimension: str | None
    cohort_value: str | None
    observed_value: JsonValue
    unit: str | None
    sample_size: int | None
    direction: EvidenceDirection
    materiality: str | None
    confidence: EvidenceConfidence
    warnings: tuple[str, ...]
    source_pointer: str


class ResearchContradiction(OpportunityModel):
    contradiction_id: str
    evidence_ids: tuple[str, ...]
    nature: str
    affected_dimensions: tuple[str, ...]
    unresolved_question: str
    future_discovery_need: str


class OpportunityRule(OpportunityModel):
    rule_id: str
    version: str
    archetype: OpportunityArchetypeId
    workflow_stage: str
    required_evidence: tuple[str, ...]
    optional_evidence: tuple[str, ...]
    minimum_sample_size: int
    materiality_threshold: str
    exclusion_conditions: tuple[str, ...]
    cohort_dimension: str


class ObservedBurden(OpportunityModel):
    affected_case_count: int | None
    affected_case_rate: float | None
    period_normalised_cases: float | None
    observed_manual_touches: float | None
    estimated_manual_touch_hours: float | None
    rework_events: int | None
    handoffs: float | None
    elapsed_delay_hours: float | None
    business_delay_hours: float | None
    stuck_case_count: int | None
    associated_admin_cost_gbp: float | None
    addressable_upper_bound_gbp: float | None
    expected_benefit_gbp: None = None
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]


class AssessmentComponent(OpportunityModel):
    name: str
    score: float
    rationale: str


class ValueAssessment(OpportunityModel):
    components: tuple[AssessmentComponent, ...]
    score: float
    classification: str
    raw_measures: dict[str, float | int | None]
    normalisation: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]


class ReadinessAssessment(OpportunityModel):
    components: tuple[AssessmentComponent, ...]
    score: float
    classification: str
    limitations: tuple[str, ...]


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    PROHIBITED = "prohibited"


class RequiredControl(StrEnum):
    OBSERVE_ONLY = "observe_only"
    RECOMMENDATION_ONLY = "recommendation_only"
    HUMAN_APPROVAL = "human_approval_required"
    LIMITED_SANDBOX = "limited_action_sandbox"
    REVERSIBLE_ACTION = "reversible_action_required"
    AUDIT_TRAIL = "audit_trail_required"
    MANUAL_FALLBACK = "manual_fallback_required"
    RATE_LIMIT = "rate_limit_required"
    PROHIBIT_AUTONOMOUS_EXECUTION = "prohibited_from_autonomous_execution"


class RiskAssessment(OpportunityModel):
    components: tuple[AssessmentComponent, ...]
    score: float
    level: RiskLevel
    required_controls: tuple[RequiredControl, ...]
    failure_modes: tuple[str, ...]


class ConfidenceAssessment(OpportunityModel):
    score: float
    classification: str
    supporting_factors: tuple[str, ...]
    reducing_factors: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    evidence_gaps: tuple[str, ...]


class EligibilityStatus(StrEnum):
    CONTROLLED_PROTOTYPE = "eligible_for_controlled_prototype"
    FURTHER_DISCOVERY = "eligible_for_further_discovery"
    NEEDS_EVIDENCE = "needs_additional_evidence"
    BLOCKED_GOVERNANCE = "blocked_by_governance"
    BLOCKED_DATA = "blocked_by_data_readiness"
    OUT_OF_SCOPE = "out_of_scope"
    INELIGIBLE = "ineligible"


class EligibilityGate(OpportunityModel):
    gate: str
    passed: bool
    rationale: str


class EligibilityAssessment(OpportunityModel):
    status: EligibilityStatus
    gates: tuple[EligibilityGate, ...]
    hard_failure: bool
    reasons: tuple[str, ...]


class OpportunityScore(OpportunityModel):
    value_contribution: float
    readiness_contribution: float
    confidence_contribution: float
    risk_penalty: float
    priority_score: float | None
    formula: str
    tie_breaker: str


class PortfolioSection(StrEnum):
    CONTROLLED_PROTOTYPE = "eligible_for_controlled_prototype"
    FURTHER_DISCOVERY = "needs_further_discovery"
    BLOCKED = "blocked_or_out_of_scope"


class OpportunityCandidate(OpportunityModel):
    opportunity_id: str
    opportunity_model_version: str
    rule_ids: tuple[str, ...]
    archetype: OpportunityArchetypeId
    title: str
    cohort_dimension: str
    cohort_value: str
    workflow_stage: str
    problem_statement: str
    observed_burden: ObservedBurden
    quantitative_evidence_ids: tuple[str, ...]
    qualitative_evidence_ids: tuple[str, ...]
    contradiction_ids: tuple[str, ...]
    eligibility: EligibilityAssessment
    value: ValueAssessment
    readiness: ReadinessAssessment
    risk: RiskAssessment
    confidence: ConfidenceAssessment
    score: OpportunityScore
    portfolio_section: PortfolioSection
    portfolio_position: int | None
    future_success_metrics: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    warnings: tuple[str, ...]
    source_artifact_fingerprints: tuple[str, ...]


class EvidenceQualitySummary(OpportunityModel):
    total_evidence_count: int
    quantitative_evidence_count: int
    qualitative_evidence_count: int
    contradiction_count: int
    warning_count: int
    research_session_count: int
    research_observation_count: int


class PortfolioSummary(OpportunityModel):
    candidate_count_before_deduplication: int
    candidate_count_after_deduplication: int
    controlled_prototype_ids: tuple[str, ...]
    further_discovery_ids: tuple[str, ...]
    blocked_ids: tuple[str, ...]


class OpportunityBenchmarkResult(OpportunityModel):
    expected_opportunity: str
    detected: bool
    opportunity_id: str | None
    expected_archetype: OpportunityArchetypeId
    expected_cohort: str
    evidence_references_valid: bool
    research_linked: bool
    controls_appropriate: bool
    portfolio_section_appropriate: bool


class OpportunityBenchmarkEvaluation(OpportunityModel):
    status: str
    results: tuple[OpportunityBenchmarkResult, ...]
    detected_count: int
    expected_count: int
    false_negatives: tuple[str, ...]
    unexpected_opportunity_ids: tuple[str, ...]
    notes: tuple[str, ...]


class PortfolioPoint(OpportunityModel):
    opportunity_id: str
    value_score: float
    readiness_score: float
    confidence_score: float
    risk_score: float
    priority_score: float | None
    eligibility: EligibilityStatus
    portfolio_section: PortfolioSection
    affected_case_count: int | None
    archetype: OpportunityArchetypeId
    cohort_dimension: str
    cohort_value: str
    evidence_count: int


class EvidenceNetworkNode(OpportunityModel):
    node_id: str
    node_type: str
    label: str
    source_pointer: str | None


class EvidenceNetworkLink(OpportunityModel):
    link_id: str
    source_node_id: str
    target_node_id: str
    relationship: str


class OpportunityGraphData(OpportunityModel):
    portfolio_points: tuple[PortfolioPoint, ...]
    evidence_nodes: tuple[EvidenceNetworkNode, ...]
    evidence_links: tuple[EvidenceNetworkLink, ...]


class OpportunityAnalysis(OpportunityModel):
    analysis_version: str
    analysis_id: str
    source_dataset_fingerprint: str
    baseline_analysis_fingerprint: str
    process_analysis_fingerprint: str
    generation_run_id: str | None
    research_pack_version: str
    research_pack_fingerprint: str
    archetype_library_version: str
    rule_library_version: str
    scoring_model_version: str
    configuration: dict[str, JsonValue]
    analysed_at: datetime
    evidence_quality: EvidenceQualitySummary
    evidence_references: tuple[EvidenceReference, ...]
    contradictions: tuple[ResearchContradiction, ...]
    candidates: tuple[OpportunityCandidate, ...]
    portfolio: PortfolioSummary
    benchmark_evaluation: OpportunityBenchmarkEvaluation
    graph_data: OpportunityGraphData
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    warnings: tuple[str, ...]
    opportunity_analysis_fingerprint: str
    fictional_data_confirmation: str


@dataclass(frozen=True, slots=True)
class OpportunityAnalysisInput:
    baseline: BaselineAnalysis
    process: ProcessMiningAnalysis
    research: ResearchPack
    manifest: GenerationManifest | None = None
    ground_truth: GenerationGroundTruth | None = None
