"""Administrative and safety gates that operate outside portfolio scoring."""

from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.models import (
    EligibilityAssessment,
    EligibilityGate,
    EligibilityStatus,
    OpportunityArchetypeId,
)
from workflowtwin.opportunities.rules import OpportunitySeed

PROTOTYPE_ARCHETYPES = {
    OpportunityArchetypeId.INTAKE_COMPLETENESS,
    OpportunityArchetypeId.STUCK_CASE_MONITORING,
    OpportunityArchetypeId.DATA_QUALITY_MONITORING,
}


def assess_eligibility(
    seed: OpportunitySeed,
    config: OpportunityConfig,
    *,
    requires_clinical_judgement: bool = False,
    requires_sensitive_data: bool = False,
) -> EligibilityAssessment:
    quantitative_count = len(seed.quantitative_evidence_ids)
    gates = (
        EligibilityGate(
            gate="administrative_scope",
            passed=not requires_clinical_judgement,
            rationale="archetype is restricted to administrative workflow fields",
        ),
        EligibilityGate(
            gate="evidence_sufficiency",
            passed=quantitative_count >= config.minimum_quantitative_evidence,
            rationale=f"{quantitative_count} quantitative evidence references are linked",
        ),
        EligibilityGate(
            gate="data_availability",
            passed=quantitative_count > 0,
            rationale="required metrics are represented as structured evidence",
        ),
        EligibilityGate(
            gate="process_stability",
            passed=seed.archetype
            not in {
                OpportunityArchetypeId.ASSIGNMENT_ROUTING,
                OpportunityArchetypeId.HANDOFF_REDUCTION,
            },
            rationale="routing and handoff exceptions require further observation",
        ),
        EligibilityGate(
            gate="measurability",
            passed=True,
            rationale="existing baseline metrics can measure future success and failure",
        ),
        EligibilityGate(
            gate="reversibility",
            passed=True,
            rationale=(
                "future prototype is constrained to observe or recommend with manual fallback"
            ),
        ),
        EligibilityGate(
            gate="human_oversight",
            passed=True,
            rationale="the archetype defines staff review or approval",
        ),
        EligibilityGate(
            gate="auditability",
            passed=True,
            rationale="stable evidence and opportunity identifiers support an audit trail",
        ),
        EligibilityGate(
            gate="clinical_exclusion",
            passed=not requires_clinical_judgement,
            rationale="medical judgement and inferred clinical information are prohibited",
        ),
        EligibilityGate(
            gate="sensitive_data_exposure",
            passed=not requires_sensitive_data,
            rationale="only minimum structured administrative evidence is permitted",
        ),
    )
    hard_failure = requires_clinical_judgement or requires_sensitive_data
    if hard_failure:
        status = (
            EligibilityStatus.OUT_OF_SCOPE
            if requires_clinical_judgement
            else EligibilityStatus.INELIGIBLE
        )
        reasons = ("hard safety exclusion cannot be overridden by value or ranking",)
    elif quantitative_count < config.minimum_quantitative_evidence:
        status = EligibilityStatus.NEEDS_EVIDENCE
        reasons = ("insufficient independent quantitative evidence",)
    elif seed.archetype in PROTOTYPE_ARCHETYPES:
        status = EligibilityStatus.CONTROLLED_PROTOTYPE
        reasons = ("bounded administrative prototype is measurable with explicit controls",)
    else:
        status = EligibilityStatus.FURTHER_DISCOVERY
        reasons = ("exceptions, integration readiness, or action rules need further discovery",)
    return EligibilityAssessment(
        status=status,
        gates=gates,
        hard_failure=hard_failure,
        reasons=reasons,
    )
