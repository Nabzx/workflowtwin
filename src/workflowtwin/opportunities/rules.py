"""Transparent rules mapping existing evidence into opportunity seeds."""

from dataclasses import dataclass

from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.models import (
    EvidenceReference,
    EvidenceSourceType,
    OpportunityAnalysisInput,
    OpportunityArchetypeId,
    OpportunityRule,
)

RULE_LIBRARY_VERSION = "northstar-opportunity-rules-v1"


@dataclass(frozen=True, slots=True)
class OpportunitySeed:
    rule_ids: tuple[str, ...]
    archetype: OpportunityArchetypeId
    cohort_dimension: str
    cohort_value: str
    workflow_stage: str
    problem_statement: str
    quantitative_evidence_ids: tuple[str, ...]
    qualitative_evidence_ids: tuple[str, ...]


RULES = (
    OpportunityRule(
        rule_id="rule-intake-completeness-v1",
        version="1.0.0",
        archetype=OpportunityArchetypeId.INTAKE_COMPLETENESS,
        workflow_stage="intake_completeness",
        required_evidence=(
            "baseline completeness or rework finding",
            "process missing-information evidence",
        ),
        optional_evidence=("repeated checks", "administrator observation"),
        minimum_sample_size=20,
        materiality_threshold="material baseline difference and process association",
        exclusion_conditions=("clinical content required", "insufficient cohort volume"),
        cohort_dimension="referral_source",
    ),
    OpportunityRule(
        rule_id="rule-assignment-routing-v1",
        version="1.0.0",
        archetype=OpportunityArchetypeId.ASSIGNMENT_ROUTING,
        workflow_stage="assignment",
        required_evidence=("baseline assignment delay", "process assignment-delay candidate"),
        optional_evidence=(
            "stuck cases",
            "operations observation",
            "coordinator exception evidence",
        ),
        minimum_sample_size=20,
        materiality_threshold="material assignment delay",
        exclusion_conditions=("clinical routing inference required",),
        cohort_dimension="service_line",
    ),
    OpportunityRule(
        rule_id="rule-scheduling-coordination-v1",
        version="1.0.0",
        archetype=OpportunityArchetypeId.SCHEDULING_COORDINATION,
        workflow_stage="scheduling",
        required_evidence=("baseline scheduling finding", "process retry candidate"),
        optional_evidence=("retry loop", "non-response", "scheduler observation"),
        minimum_sample_size=20,
        materiality_threshold="material failed-scheduling difference",
        exclusion_conditions=("autonomous booking or communication required",),
        cohort_dimension="service_line",
    ),
    OpportunityRule(
        rule_id="rule-handoff-reduction-v1",
        version="1.0.0",
        archetype=OpportunityArchetypeId.HANDOFF_REDUCTION,
        workflow_stage="assignment",
        required_evidence=(
            "baseline handoff or reassignment finding",
            "process reassignment candidate",
        ),
        optional_evidence=("handoff transition", "service coordinator observation"),
        minimum_sample_size=20,
        materiality_threshold="material reassignment or handoff difference",
        exclusion_conditions=("valid specialist handoffs cannot be distinguished",),
        cohort_dimension="service_line",
    ),
    OpportunityRule(
        rule_id="rule-stuck-case-monitoring-v1",
        version="1.0.0",
        archetype=OpportunityArchetypeId.STUCK_CASE_MONITORING,
        workflow_stage="cross_workflow_monitoring",
        required_evidence=("missing-terminal deviations", "measurable open-case volume"),
        optional_evidence=("scheduler observation",),
        minimum_sample_size=20,
        materiality_threshold="minimum stalled case count",
        exclusion_conditions=("monitor would infer clinical risk",),
        cohort_dimension="overall",
    ),
    OpportunityRule(
        rule_id="rule-data-quality-monitoring-v1",
        version="1.0.0",
        archetype=OpportunityArchetypeId.DATA_QUALITY_MONITORING,
        workflow_stage="ingestion",
        required_evidence=(
            "delayed or out-of-order event count",
            "traceable source quality evidence",
        ),
        optional_evidence=("integration-lead observation", "source retry manifest evidence"),
        minimum_sample_size=20,
        materiality_threshold="minimum affected event or case count",
        exclusion_conditions=("used to rank employee performance",),
        cohort_dimension="source_system",
    ),
)


def _matches_cohort(evidence: EvidenceReference, dimension: str, value: str) -> bool:
    return (
        evidence.cohort_dimension == dimension and evidence.cohort_value == value
    ) or evidence.cohort_dimension is None


def _evidence_ids(
    evidence: tuple[EvidenceReference, ...],
    *,
    source_types: set[EvidenceSourceType],
    dimension: str,
    value: str,
    terms: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        item.evidence_id
        for item in evidence
        if item.source_type in source_types
        and _matches_cohort(item, dimension, value)
        and any(term in item.metric_or_observation for term in terms)
    )


def _research_ids(
    analysis_input: OpportunityAnalysisInput,
    evidence: tuple[EvidenceReference, ...],
    archetype: OpportunityArchetypeId,
    dimension: str,
    value: str,
) -> tuple[str, ...]:
    supported = {
        observation.observation_id
        for session in analysis_input.research.sessions
        for observation in session.observations
        if archetype in observation.supported_archetypes
        and (
            observation.cohort_dimension is None
            or (observation.cohort_dimension == dimension and observation.cohort_value == value)
        )
    }
    return tuple(
        item.evidence_id
        for item in evidence
        if item.source_type is EvidenceSourceType.RESEARCH_OBSERVATION
        and item.source_record_id in supported
    )


def _cohort_process_ids(
    evidence: tuple[EvidenceReference, ...],
    dimension: str,
    value: str,
    terms: tuple[str, ...],
) -> tuple[str, ...]:
    return _evidence_ids(
        evidence,
        source_types={
            EvidenceSourceType.PROCESS_CANDIDATE,
            EvidenceSourceType.PROCESS_TRANSITION,
            EvidenceSourceType.PROCESS_VARIANT,
            EvidenceSourceType.PROCESS_DEVIATION,
        },
        dimension=dimension,
        value=value,
        terms=terms,
    )


def trigger_opportunity_rules(
    analysis_input: OpportunityAnalysisInput,
    evidence: tuple[EvidenceReference, ...],
    config: OpportunityConfig,
) -> tuple[OpportunitySeed, ...]:
    baseline = analysis_input.baseline
    process = analysis_input.process
    seeds = []
    baseline_patterns = (
        (
            OpportunityArchetypeId.INTAKE_COMPLETENESS,
            "referral_source",
            {"lower_first_pass_completeness", "elevated_rework"},
            "intake_completeness",
            ("referral_source_rework_path", "Missing information", "missing_information"),
            "The referral-source cohort contains lower completeness and repeated "
            "administrative information work.",
            "rule-intake-completeness-v1",
        ),
        (
            OpportunityArchetypeId.ASSIGNMENT_ROUTING,
            "service_line",
            {"longer_assignment_wait"},
            "assignment",
            ("service_line_assignment_delay", "Referral categorised -> Clinical team assigned"),
            "The service line contains elevated administrative assignment delay.",
            "rule-assignment-routing-v1",
        ),
        (
            OpportunityArchetypeId.SCHEDULING_COORDINATION,
            "service_line",
            {"elevated_failed_scheduling", "longer_booking_time", "elevated_rework"},
            "scheduling",
            ("service_line_scheduling_retries", "Scheduling failed", "failed_scheduling"),
            "The service line contains repeated failed scheduling and additional "
            "coordination burden.",
            "rule-scheduling-coordination-v1",
        ),
        (
            OpportunityArchetypeId.HANDOFF_REDUCTION,
            "service_line",
            {"elevated_reassignment", "elevated_handoffs"},
            "assignment",
            ("service_line_reassignment", "Clinical team reassigned", "reassignment"),
            "The service line contains elevated reassignment and administrative handoff burden.",
            "rule-handoff-reduction-v1",
        ),
    )
    for (
        archetype,
        dimension,
        finding_types,
        stage,
        process_terms,
        statement,
        rule_id,
    ) in baseline_patterns:
        for finding in baseline.findings:
            if (
                finding.finding_type not in finding_types
                or finding.cohort_dimension != dimension
                or finding.cohort_size < config.minimum_sample_size
            ):
                continue
            process_ids = _cohort_process_ids(
                evidence, dimension, finding.cohort_value, process_terms
            )
            if not process_ids:
                continue
            baseline_ids = _evidence_ids(
                evidence,
                source_types={
                    EvidenceSourceType.BASELINE_FINDING,
                    EvidenceSourceType.COHORT_METRIC,
                },
                dimension=dimension,
                value=finding.cohort_value,
                terms=(finding.metric_name,),
            )
            seeds.append(
                OpportunitySeed(
                    rule_ids=(rule_id,),
                    archetype=archetype,
                    cohort_dimension=dimension,
                    cohort_value=finding.cohort_value,
                    workflow_stage=stage,
                    problem_statement=statement,
                    quantitative_evidence_ids=tuple(sorted(set((*baseline_ids, *process_ids)))),
                    qualitative_evidence_ids=_research_ids(
                        analysis_input,
                        evidence,
                        archetype,
                        dimension,
                        finding.cohort_value,
                    ),
                )
            )
    missing_terminal = process.deviation_summary.get("missing_terminal_event", 0)
    if missing_terminal >= config.minimum_sample_size:
        quantitative = _evidence_ids(
            evidence,
            source_types={EvidenceSourceType.PROCESS_DEVIATION, EvidenceSourceType.COHORT_METRIC},
            dimension="overall",
            value="all",
            terms=("missing_terminal_event", "stuck_case_rate", "is_stuck"),
        )
        seeds.append(
            OpportunitySeed(
                rule_ids=("rule-stuck-case-monitoring-v1",),
                archetype=OpportunityArchetypeId.STUCK_CASE_MONITORING,
                cohort_dimension="overall",
                cohort_value="all_cases",
                workflow_stage="cross_workflow_monitoring",
                problem_statement=(
                    "Open administrative cases and missing terminal events require "
                    "consistent review."
                ),
                quantitative_evidence_ids=quantitative,
                qualitative_evidence_ids=_research_ids(
                    analysis_input,
                    evidence,
                    OpportunityArchetypeId.STUCK_CASE_MONITORING,
                    "overall",
                    "all_cases",
                ),
            )
        )
    delayed = baseline.quality.delayed_ingestion_cases
    out_of_order = baseline.quality.out_of_order_ingestion_cases
    if max(delayed, out_of_order) >= config.minimum_sample_size:
        quantitative = _evidence_ids(
            evidence,
            source_types={EvidenceSourceType.BASELINE_QUALITY, EvidenceSourceType.PROCESS_QUALITY},
            dimension="source_system",
            value="all_sources",
            terms=("delayed_ingestion", "out_of_order_ingestion", "duplicate_events"),
        )
        seeds.append(
            OpportunitySeed(
                rule_ids=("rule-data-quality-monitoring-v1",),
                archetype=OpportunityArchetypeId.DATA_QUALITY_MONITORING,
                cohort_dimension="source_system",
                cohort_value="all_sources",
                workflow_stage="ingestion",
                problem_statement=(
                    "Delayed and out-of-order source events reduce confidence in observed "
                    "workflow order."
                ),
                quantitative_evidence_ids=quantitative,
                qualitative_evidence_ids=_research_ids(
                    analysis_input,
                    evidence,
                    OpportunityArchetypeId.DATA_QUALITY_MONITORING,
                    "source_system",
                    "all_sources",
                ),
            )
        )
    return tuple(seeds)
