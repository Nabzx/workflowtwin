"""Versioned library of bounded administrative automation archetypes."""

from workflowtwin.opportunities.models import (
    EvidenceSourceType,
    OpportunityArchetype,
    OpportunityArchetypeId,
    OversightClass,
)

ARCHETYPE_LIBRARY_VERSION = "northstar-archetypes-v1"
QUANTITATIVE = (
    EvidenceSourceType.BASELINE_FINDING,
    EvidenceSourceType.COHORT_METRIC,
    EvidenceSourceType.PROCESS_TRANSITION,
    EvidenceSourceType.PROCESS_VARIANT,
    EvidenceSourceType.PROCESS_CANDIDATE,
    EvidenceSourceType.PROCESS_DEVIATION,
)


def _archetype(
    archetype_id: OpportunityArchetypeId,
    title: str,
    purpose: str,
    action: str,
    oversight: OversightClass,
    measures: tuple[str, ...],
    failures: tuple[str, ...],
    restrictions: tuple[str, ...],
) -> OpportunityArchetype:
    return OpportunityArchetype(
        archetype_id=archetype_id,
        version="1.0.0",
        title=title,
        operational_purpose=purpose,
        applicable_evidence_types=(*QUANTITATIVE, EvidenceSourceType.RESEARCH_OBSERVATION),
        minimum_eligibility_conditions=(
            "administrative scope",
            "traceable operational evidence",
            "measurable success and failure",
            "human oversight and audit trail available",
        ),
        disqualifying_conditions=(
            "requires medical judgement or clinical urgency inference",
            "requires covert surveillance or employee ranking",
            "requires unrestricted identifiable patient data",
        ),
        likely_action_class=action,
        oversight_class=oversight,
        success_measures=measures,
        known_failure_modes=failures,
        safety_restrictions=restrictions,
    )


ARCHETYPES = (
    _archetype(
        OpportunityArchetypeId.INTAKE_COMPLETENESS,
        "Intake completeness validation",
        "Detect missing required administrative fields before manual review.",
        "structured validation and staff prompt",
        OversightClass.HUMAN_REVIEW,
        (
            "first_pass_completeness_rate",
            "missing_information_request_rate",
            "manual_touches",
            "time_to_first_completeness_check_hours",
        ),
        ("valid referrals incorrectly blocked", "source-specific requirements become stale"),
        ("no diagnosis inference", "no autonomous external communication"),
    ),
    _archetype(
        OpportunityArchetypeId.CLASSIFICATION_ASSISTANCE,
        "Administrative classification assistance",
        "Suggest or validate administrative categories from explicit structured fields.",
        "staff-facing category suggestion",
        OversightClass.HUMAN_APPROVAL,
        ("recategorisation_count", "reassignment_count", "manual_touches"),
        ("silent misclassification", "structured fields are incomplete"),
        ("no clinical urgency, diagnosis, or free-text inference",),
    ),
    _archetype(
        OpportunityArchetypeId.ASSIGNMENT_ROUTING,
        "Assignment and routing assistance",
        "Support administrative routing to an operational team using explicit rules.",
        "staff-facing routing suggestion",
        OversightClass.HUMAN_APPROVAL,
        (
            "assignment_wait_business_hours",
            "reassignment_count",
            "handoffs",
            "assignment_related_stuck_cases",
        ),
        ("silent misrouting", "exceptions bypass ordinary routing rules"),
        ("explicit fields only", "no autonomous clinical prioritisation"),
    ),
    _archetype(
        OpportunityArchetypeId.SCHEDULING_COORDINATION,
        "Scheduling coordination assistance",
        "Support retry queues and administrative scheduling follow-up.",
        "staff work queue and retry coordination",
        OversightClass.HUMAN_APPROVAL,
        (
            "failed_scheduling_attempts",
            "time_to_appointment_booking_hours",
            "manual_scheduling_touches",
            "non_response_closure_rate",
        ),
        ("duplicate booking", "incorrect patient-facing action", "silent retry failure"),
        ("no autonomous booking", "no automated patient communication"),
    ),
    _archetype(
        OpportunityArchetypeId.STUCK_CASE_MONITORING,
        "Stuck-case monitoring",
        "Flag administratively stalled cases for staff review.",
        "observe-only monitoring alert",
        OversightClass.OBSERVE_ONLY,
        ("stuck_case_rate", "open_case_age_hours", "missing_terminal_event_count"),
        ("alert fatigue", "incorrect threshold due to missing events"),
        ("no clinical-risk interpretation", "team-level workflow monitoring only"),
    ),
    _archetype(
        OpportunityArchetypeId.DATA_QUALITY_MONITORING,
        "Data-quality and ingestion monitoring",
        "Identify delayed, out-of-order, repeated, or unsupported source events.",
        "observe-only source quality alert",
        OversightClass.OBSERVE_ONLY,
        ("delayed_ingestion_rate", "out_of_order_ingestion_rate", "duplicate_event_count"),
        ("false alerts during known source maintenance", "timestamps remain unreliable"),
        ("no employee performance inference", "no operational outcome claim"),
    ),
    _archetype(
        OpportunityArchetypeId.HANDOFF_REDUCTION,
        "Administrative handoff reduction",
        "Make ownership changes transparent and reduce avoidable reassignment.",
        "staff-facing ownership suggestion",
        OversightClass.HUMAN_APPROVAL,
        ("reassignment_count", "handoffs", "cycle_time_hours", "ownership_changes"),
        ("needed specialist handoffs suppressed", "ownership becomes ambiguous"),
        ("no individual employee ranking", "manual override required"),
    ),
)

ARCHETYPE_BY_ID = {item.archetype_id: item for item in ARCHETYPES}
