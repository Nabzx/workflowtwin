"""Operational and governance risk with mandatory controls."""

from workflowtwin.opportunities.models import (
    AssessmentComponent,
    OpportunityArchetypeId,
    RequiredControl,
    RiskAssessment,
    RiskLevel,
)


def assess_risk(archetype: OpportunityArchetypeId) -> RiskAssessment:
    profiles = {
        OpportunityArchetypeId.INTAKE_COMPLETENESS: (40.0, RiskLevel.MODERATE),
        OpportunityArchetypeId.ASSIGNMENT_ROUTING: (72.0, RiskLevel.HIGH),
        OpportunityArchetypeId.SCHEDULING_COORDINATION: (75.0, RiskLevel.HIGH),
        OpportunityArchetypeId.STUCK_CASE_MONITORING: (22.0, RiskLevel.LOW),
        OpportunityArchetypeId.DATA_QUALITY_MONITORING: (18.0, RiskLevel.LOW),
        OpportunityArchetypeId.HANDOFF_REDUCTION: (58.0, RiskLevel.MODERATE),
    }
    score, level = profiles.get(archetype, (80.0, RiskLevel.HIGH))
    customer_facing = 80.0 if archetype is OpportunityArchetypeId.SCHEDULING_COORDINATION else 25.0
    ambiguity = (
        80.0
        if archetype
        in {OpportunityArchetypeId.ASSIGNMENT_ROUTING, OpportunityArchetypeId.HANDOFF_REDUCTION}
        else 35.0
    )
    components = (
        AssessmentComponent(
            name="incorrect_action_consequence",
            score=score,
            rationale="bounded archetype risk profile",
        ),
        AssessmentComponent(
            name="customer_facing_impact",
            score=customer_facing,
            rationale="future external action is prohibited or approval-gated",
        ),
        AssessmentComponent(
            name="ambiguity_and_exceptions",
            score=ambiguity,
            rationale="research disagreement and exception frequency",
        ),
        AssessmentComponent(
            name="data_sensitivity",
            score=45,
            rationale="minimum administrative data is still sensitive",
        ),
        AssessmentComponent(
            name="silent_failure",
            score=score,
            rationale="audit and monitoring controls are mandatory",
        ),
    )
    controls = {
        RequiredControl.AUDIT_TRAIL,
        RequiredControl.MANUAL_FALLBACK,
        RequiredControl.PROHIBIT_AUTONOMOUS_EXECUTION,
    }
    if level in {RiskLevel.MODERATE, RiskLevel.HIGH}:
        controls.update(
            {
                RequiredControl.RECOMMENDATION_ONLY,
                RequiredControl.HUMAN_APPROVAL,
                RequiredControl.REVERSIBLE_ACTION,
            }
        )
    else:
        controls.add(RequiredControl.OBSERVE_ONLY)
    if level is RiskLevel.HIGH:
        controls.update({RequiredControl.LIMITED_SANDBOX, RequiredControl.RATE_LIMIT})
    return RiskAssessment(
        components=components,
        score=score,
        level=level,
        required_controls=tuple(sorted(controls, key=lambda item: item.value)),
        failure_modes=(
            "incorrect administrative suggestion",
            "legitimate exception hidden",
            "silent failure or stale rule",
        ),
    )
