"""Explicit recommendation, review, failure, fallback, and rollback policy."""

from dataclasses import dataclass
from random import Random

from workflowtwin.simulation.config import SimulationConfig
from workflowtwin.simulation.models import (
    CaseEligibility,
    InterventionAction,
    InterventionDecision,
    PolicyDecisionStatus,
)


@dataclass(frozen=True, slots=True)
class PolicyOutcome:
    decision: InterventionDecision
    detector_outcome: str
    effective_action: bool


def _decision(
    eligibility: CaseEligibility,
    config: SimulationConfig,
    *,
    status: PolicyDecisionStatus,
    reasons: tuple[str, ...],
    action: InterventionAction | None,
    review_hours: float | None = None,
    overhead: float = 0.0,
    warnings: tuple[str, ...] = (),
) -> InterventionDecision:
    return InterventionDecision(
        case_id=eligibility.case_id,
        policy_version=config.policy_version,
        status=status,
        reason_codes=reasons,
        relevant_event_ids=eligibility.trigger_event_ids,
        triggering_evidence=("referral_source=gp_practice", "structured_event_history=v1"),
        assumptions=(
            "decision is fictional and simulated",
            "policy never receives the simulation-only hidden truth label",
        ),
        required_reviewer_role=("referral_administrator" if action is not None else None),
        simulated_action=action,
        review_turnaround_hours=review_hours,
        manual_touch_overhead=overhead,
        warnings=warnings,
    )


def apply_policy(
    eligibility: CaseEligibility,
    *,
    hidden_incomplete: bool,
    config: SimulationConfig,
    random: Random,
) -> PolicyOutcome:
    """Return a final audited state; hidden truth only drives detector simulation."""
    parameters = config.parameters
    if not eligibility.eligible:
        return PolicyOutcome(
            _decision(
                eligibility,
                config,
                status=PolicyDecisionStatus.NOT_ELIGIBLE,
                reasons=eligibility.reason_codes,
                action=None,
            ),
            "not_evaluated",
            False,
        )
    if random.random() >= parameters.rollout_percentage:
        return PolicyOutcome(
            _decision(
                eligibility,
                config,
                status=PolicyDecisionStatus.OBSERVE_ONLY,
                reasons=("outside_deterministic_rollout_sample",),
                action=InterventionAction.OBSERVE_STRUCTURED_FIELDS,
            ),
            "observe_only",
            False,
        )
    if random.random() < parameters.intervention_failure_rate:
        return PolicyOutcome(
            _decision(
                eligibility,
                config,
                status=PolicyDecisionStatus.SIMULATION_FAILURE,
                reasons=("intervention_service_unavailable", "manual_fallback_required"),
                action=InterventionAction.FALLBACK_TO_MANUAL,
                overhead=0.5,
                warnings=("simulated service failure retained the source path",),
            ),
            "service_failure",
            False,
        )

    positive = (
        random.random() >= parameters.false_negative_rate
        if hidden_incomplete
        else random.random() < parameters.false_positive_rate
    )
    detector_outcome = (
        "true_positive"
        if positive and hidden_incomplete
        else "false_positive"
        if positive
        else "false_negative"
        if hidden_incomplete
        else "true_negative"
    )
    if not positive:
        return PolicyOutcome(
            _decision(
                eligibility,
                config,
                status=PolicyDecisionStatus.OBSERVE_ONLY,
                reasons=(detector_outcome, "source_workflow_retained"),
                action=InterventionAction.OBSERVE_STRUCTURED_FIELDS,
            ),
            detector_outcome,
            False,
        )

    review_hours = random.uniform(*parameters.human_review_turnaround_hours)
    if random.random() < parameters.human_review_timeout_rate:
        return PolicyOutcome(
            _decision(
                eligibility,
                config,
                status=PolicyDecisionStatus.FALLBACK_TO_MANUAL,
                reasons=(detector_outcome, "reviewer_timeout", "manual_fallback_required"),
                action=InterventionAction.FALLBACK_TO_MANUAL,
                review_hours=review_hours,
                overhead=1.5,
            ),
            detector_outcome,
            False,
        )
    if random.random() >= parameters.human_review_acceptance_rate:
        return PolicyOutcome(
            _decision(
                eligibility,
                config,
                status=PolicyDecisionStatus.REJECTED_BY_REVIEWER,
                reasons=(detector_outcome, "reviewer_rejected_recommendation"),
                action=InterventionAction.REQUEST_HUMAN_APPROVAL,
                review_hours=review_hours,
                overhead=1.0,
            ),
            detector_outcome,
            False,
        )
    if not hidden_incomplete:
        return PolicyOutcome(
            _decision(
                eligibility,
                config,
                status=PolicyDecisionStatus.ROLLED_BACK,
                reasons=("false_positive", "prohibited_external_action_prevented"),
                action=InterventionAction.ROLLBACK,
                review_hours=review_hours + parameters.rollback_recovery_delay_hours,
                overhead=2.0,
                warnings=("no missing-information request was inserted",),
            ),
            detector_outcome,
            False,
        )
    if random.random() < parameters.manual_fallback_rate:
        return PolicyOutcome(
            _decision(
                eligibility,
                config,
                status=PolicyDecisionStatus.FALLBACK_TO_MANUAL,
                reasons=("true_positive", "manual_fallback_sampled"),
                action=InterventionAction.FALLBACK_TO_MANUAL,
                review_hours=review_hours,
                overhead=1.0,
            ),
            detector_outcome,
            False,
        )
    if random.random() < parameters.rollback_rate:
        return PolicyOutcome(
            _decision(
                eligibility,
                config,
                status=PolicyDecisionStatus.ROLLED_BACK,
                reasons=("true_positive", "post_approval_rollback_sampled"),
                action=InterventionAction.ROLLBACK,
                review_hours=review_hours + parameters.rollback_recovery_delay_hours,
                overhead=2.0,
            ),
            detector_outcome,
            False,
        )
    effective = random.random() < parameters.effectiveness
    return PolicyOutcome(
        _decision(
            eligibility,
            config,
            status=PolicyDecisionStatus.APPROVED_SIMULATED_ACTION,
            reasons=(
                "true_positive",
                "human_approval_recorded",
                "effective_rule_application" if effective else "limited_rule_effect",
            ),
            action=InterventionAction.RECORD_APPROVED_VALIDATION,
            review_hours=review_hours,
            overhead=1.0,
        ),
        detector_outcome,
        effective,
    )
