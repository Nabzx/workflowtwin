"""Technical and operational readiness assessment."""

from workflowtwin.opportunities.models import (
    AssessmentComponent,
    OpportunityArchetypeId,
    ReadinessAssessment,
)


def assess_readiness(archetype: OpportunityArchetypeId, has_research: bool) -> ReadinessAssessment:
    stable_rules = {
        OpportunityArchetypeId.INTAKE_COMPLETENESS: 75.0,
        OpportunityArchetypeId.STUCK_CASE_MONITORING: 85.0,
        OpportunityArchetypeId.DATA_QUALITY_MONITORING: 85.0,
        OpportunityArchetypeId.SCHEDULING_COORDINATION: 55.0,
        OpportunityArchetypeId.ASSIGNMENT_ROUTING: 45.0,
        OpportunityArchetypeId.HANDOFF_REDUCTION: 50.0,
    }.get(archetype, 40.0)
    integration = (
        65.0
        if archetype
        in {
            OpportunityArchetypeId.STUCK_CASE_MONITORING,
            OpportunityArchetypeId.DATA_QUALITY_MONITORING,
        }
        else 35.0
    )
    components = (
        AssessmentComponent(
            name="structured_inputs",
            score=90,
            rationale="versioned metrics and process evidence exist",
        ),
        AssessmentComponent(
            name="action_clarity",
            score=75,
            rationale="archetype defines a bounded administrative action class",
        ),
        AssessmentComponent(
            name="event_instrumentation",
            score=90,
            rationale="existing events and fingerprints support measurement",
        ),
        AssessmentComponent(
            name="stable_process_rules",
            score=stable_rules,
            rationale="exception uncertainty varies by archetype",
        ),
        AssessmentComponent(
            name="integration_readiness",
            score=integration,
            rationale="no production action API is assumed",
        ),
        AssessmentComponent(
            name="human_review",
            score=85 if has_research else 60,
            rationale="fictional roles identify oversight needs",
        ),
        AssessmentComponent(
            name="shadow_mode",
            score=90,
            rationale="observe or recommendation-only evaluation is possible",
        ),
        AssessmentComponent(
            name="reversibility", score=90, rationale="future prototype must retain manual fallback"
        ),
    )
    score = sum(item.score for item in components) / len(components)
    classification = "high" if score >= 75 else "moderate" if score >= 55 else "low"
    limitations = ["no production integration has been demonstrated"]
    if stable_rules < 60:
        limitations.append("exception handling and operational rules need further discovery")
    return ReadinessAssessment(
        components=components,
        score=score,
        classification=classification,
        limitations=tuple(limitations),
    )
