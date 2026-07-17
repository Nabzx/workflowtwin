"""Versioned intervention design derived from the selected opportunity."""

from workflowtwin.opportunities.models import OpportunityArchetypeId, OpportunityCandidate
from workflowtwin.simulation.fingerprint import stable_hash
from workflowtwin.simulation.models import InterventionAction, InterventionDefinition

INTERVENTION_ID = "northstar-structured-completeness-review"


def define_intervention(candidate: OpportunityCandidate) -> InterventionDefinition:
    if candidate.archetype is not OpportunityArchetypeId.INTAKE_COMPLETENESS:
        raise ValueError("selected opportunity has no supported intervention definition")
    if candidate.cohort_dimension != "referral_source" or candidate.cohort_value != "gp_practice":
        raise ValueError("completeness intervention is scoped to the GP-practice cohort")
    payload = {
        "intervention_id": INTERVENTION_ID,
        "intervention_version": "1.0.0",
        "source_opportunity_id": candidate.opportunity_id,
        "opportunity_archetype": candidate.archetype.value,
        "operational_problem": candidate.problem_statement,
        "affected_cohort_dimension": candidate.cohort_dimension,
        "affected_cohort_value": candidate.cohort_value,
        "workflow_stage": candidate.workflow_stage,
        "trigger_conditions": (
            "GP-practice referral has a referral-received event",
            "version 1 structured administrative event history is available",
            "case is inside the configured simulation period and rollout cohort",
        ),
        "required_structured_inputs": (
            "referral source",
            "event schema version",
            "referral-received event",
            "structured administrative completeness indicators in a future prototype",
        ),
        "outputs": (
            "structured completeness recommendation",
            "human-review request",
            "auditable simulated decision",
        ),
        "allowed_actions": (
            InterventionAction.OBSERVE_STRUCTURED_FIELDS,
            InterventionAction.RECOMMEND_COMPLETENESS_REVIEW,
            InterventionAction.REQUEST_HUMAN_APPROVAL,
            InterventionAction.RECORD_APPROVED_VALIDATION,
            InterventionAction.FALLBACK_TO_MANUAL,
            InterventionAction.ROLLBACK,
        ),
        "prohibited_actions": (
            "no diagnosis or clinical-urgency inference",
            "no free-text clinical interpretation",
            "no autonomous external communication",
            "no service-line or clinical-team change",
            "no referral rejection, closure, or deletion",
            "no source-event mutation",
            "no protected-attribute use or employee ranking",
        ),
        "human_review_required": True,
        "required_reviewer_role": "referral_administrator",
        "escalation_conditions": (
            "missing structured administrative input",
            "stale or unsupported event sequence",
            "review timeout",
            "intervention service failure",
            "false-positive concern or policy conflict",
        ),
        "audit_requirements": (
            "record source event identifiers",
            "record policy version and reason codes",
            "record reviewer outcome and delay",
            "retain counterfactual provenance separately from source facts",
        ),
        "fallback_behaviour": "retain the complete original manual workflow",
        "rollback_behaviour": "discard simulated replacements and restore source events",
        "evaluation_metrics": candidate.future_success_metrics,
        "known_failure_modes": candidate.risk.failure_modes,
        "safety_constraints": (
            *candidate.exclusions,
            "recommendation-only with named human approval",
        ),
        "assumptions": (
            "future structured completeness indicators exist but are simulated here",
            "historical missing-information paths provide a simulation-only truth oracle",
            "review is neither instantaneous nor free",
            "all effects are fictional counterfactual estimates",
        ),
    }
    return InterventionDefinition.model_validate(
        {**payload, "definition_fingerprint": stable_hash(payload)}
    )
