"""Deterministic shadow-mode decision rules and future control requirements."""

from workflowtwin.opportunities.models import OpportunityCandidate
from workflowtwin.simulation.models import (
    PrototypeDecision,
    PrototypeDecisionStatus,
    ScenarioResult,
    SensitivityResult,
    ShadowModeRequirement,
)


def decide_shadow_mode(
    candidate: OpportunityCandidate,
    scenario: ScenarioResult,
    sensitivity: tuple[SensitivityResult, ...],
) -> PrototypeDecision:
    direct = [
        item
        for item in scenario.metric_comparisons
        if item.metric_name in {"manual_touches", "time_to_first_completeness_check_hours"}
        and item.absolute_difference is not None
    ]
    criteria = {
        "safety_eligible": not candidate.eligibility.hard_failure,
        "counterfactual_valid": scenario.quality.is_valid,
        "direct_effect_present": any(
            item.absolute_difference is not None and item.absolute_difference < 0 for item in direct
        ),
        "net_burden_positive": scenario.burden_comparison.net_simulated_difference_hours > 0,
        "within_addressable_upper_bound": (
            scenario.burden_comparison.net_simulated_difference_hours
            <= scenario.burden_comparison.addressable_upper_bound_hours
        ),
        "reversible": "reversible_action_required"
        in {control.value for control in candidate.risk.required_controls},
        "observable": bool(candidate.future_success_metrics),
        "sensitivity_not_universally_negative": any(
            item.net_burden_difference_hours > 0 for item in sensitivity
        ),
        "human_review_modelled": scenario.manifest.review_required_count > 0,
        "failure_recovery_modelled": (
            scenario.manifest.fallback_count + scenario.manifest.rollback_count > 0
        ),
    }
    if not criteria["safety_eligible"] or not criteria["counterfactual_valid"]:
        status = PrototypeDecisionStatus.DO_NOT_PROCEED
    elif all(criteria.values()):
        status = PrototypeDecisionStatus.PROCEED_SHADOW
    elif (
        criteria["direct_effect_present"]
        and (
            (criteria["net_burden_positive"] and criteria["observable"])
            or (
                scenario.scenario_id == "central"
                and criteria["sensitivity_not_universally_negative"]
            )
        )
    ):
        status = PrototypeDecisionStatus.PROCEED_WITH_CONTROLS
    elif criteria["net_burden_positive"]:
        status = PrototypeDecisionStatus.GATHER_EVIDENCE
    elif criteria["direct_effect_present"]:
        status = PrototypeDecisionStatus.REVISE
    else:
        status = PrototypeDecisionStatus.GATHER_EVIDENCE
    return PrototypeDecision(
        status=status,
        criteria=criteria,
        rationale=tuple(
            f"{name}: {'met' if passed else 'not met'}" for name, passed in sorted(criteria.items())
        ),
        required_additional_controls=(
            "shadow mode must not alter the referral workflow",
            "named administrator review and override",
            "precision, false-positive burden, latency, and policy compliance monitoring",
            "automatic stop on prohibited input, audit failure, or elevated false positives",
        ),
        tie_breaker="safety failure, validity, controls, then conservative status order",
        limitations=(
            "a proceed status supports only a future fictional shadow-mode prototype",
            "it is not deployment approval and no realised impact exists",
        ),
    )


def shadow_mode_requirements() -> tuple[ShadowModeRequirement, ...]:
    items = {
        "input_contract": "versioned structured administrative completeness fields only",
        "output_contract": "recommendation, evidence, confidence band, and no workflow mutation",
        "decision_logging": "case, policy, input version, reason codes, and timestamps",
        "human_review": "named administrator accept, reject, modify, override, and timeout states",
        "approval_policy": "no external action and no silent progression",
        "audit_trail": "append-only recommendation and review records separate from source events",
        "rollback": "disable recommendations and preserve source workflow immediately",
        "fallback": "ordinary manual completeness review remains available",
        "success_metrics": "precision, review acceptance, manual touches, and review latency",
        "failure_metrics": (
            "false positives, false negatives, timeouts, duplicate attempts, failures"
        ),
        "safety_metrics": "policy blocks, prohibited-input attempts, and audit completeness",
        "alerting": "failure-rate, false-positive, latency, and policy-compliance thresholds",
        "rollout_cohort": "fictional GP-practice cases in a bounded observation cohort",
        "observation_period": "minimum four weeks and sufficient incomplete-case volume",
        "promotion_criteria": "pre-agreed precision, burden, latency, and zero safety violations",
        "stop_conditions": "clinical input, audit gap, silent failure, excessive burden, or drift",
    }
    return tuple(
        ShadowModeRequirement(category=category, requirement=requirement)
        for category, requirement in items.items()
    )
