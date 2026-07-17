"""Case eligibility and explicit policy-state tests."""

from random import Random
from uuid import UUID

from workflowtwin.domain.referrals.enums import ReferralSource
from workflowtwin.domain.referrals.models import ReferralEvent
from workflowtwin.simulation.config import SimulationConfig
from workflowtwin.simulation.eligibility import assess_case_eligibility
from workflowtwin.simulation.interventions import define_intervention
from workflowtwin.simulation.models import (
    CaseEligibility,
    PolicyDecisionStatus,
    SimulationInput,
)
from workflowtwin.simulation.policy import apply_policy
from workflowtwin.simulation.selection import select_controlled_prototype


class SequenceRandom(Random):
    def __init__(self, values: tuple[float, ...]) -> None:
        super().__init__(0)
        self._values = iter(values)

    def random(self) -> float:
        return next(self._values)

    def uniform(self, start: float, end: float) -> float:
        return start + (end - start) * self.random()


def _eligible() -> CaseEligibility:
    return CaseEligibility(
        case_id=UUID("00000000-0000-0000-0000-000000000001"),
        eligible=True,
        reason_codes=("eligible",),
        trigger_event_ids=(),
    )


def test_case_eligibility_includes_cohort_and_explains_exclusion(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    candidate = select_controlled_prototype(demo_simulation_input.opportunities)
    definition = define_intervention(candidate)
    gp_case = next(
        case
        for case in demo_simulation_input.source.cases
        if case.referral_source is ReferralSource.GP_PRACTICE
    )
    other_case = next(
        case
        for case in demo_simulation_input.source.cases
        if case.referral_source is not ReferralSource.GP_PRACTICE
    )

    def events(case_id: UUID) -> tuple[ReferralEvent, ...]:
        return tuple(
            event
            for event in demo_simulation_input.source.events
            if event.referral_case_id == case_id
        )

    assert assess_case_eligibility(
        gp_case, events(gp_case.id), definition, central_simulation_config
    ).eligible
    excluded = assess_case_eligibility(
        other_case, events(other_case.id), definition, central_simulation_config
    )
    assert not excluded.eligible
    assert "outside_gp_practice_cohort" in excluded.reason_codes


def test_policy_not_eligible_and_observe_only(
    central_simulation_config: SimulationConfig,
) -> None:
    excluded = _eligible().model_copy(update={"eligible": False, "reason_codes": ("policy_block",)})
    assert (
        apply_policy(
            excluded,
            hidden_incomplete=True,
            config=central_simulation_config,
            random=SequenceRandom(()),
        ).decision.status
        is PolicyDecisionStatus.NOT_ELIGIBLE
    )
    observed = apply_policy(
        _eligible(),
        hidden_incomplete=True,
        config=central_simulation_config,
        random=SequenceRandom((0.99,)),
    )
    assert observed.decision.status is PolicyDecisionStatus.OBSERVE_ONLY


def test_policy_service_failure_and_false_negative(
    central_simulation_config: SimulationConfig,
) -> None:
    failure = apply_policy(
        _eligible(),
        hidden_incomplete=True,
        config=central_simulation_config,
        random=SequenceRandom((0.0, 0.0)),
    )
    assert failure.decision.status is PolicyDecisionStatus.SIMULATION_FAILURE
    false_negative = apply_policy(
        _eligible(),
        hidden_incomplete=True,
        config=central_simulation_config,
        random=SequenceRandom((0.0, 0.9, 0.0)),
    )
    assert false_negative.detector_outcome == "false_negative"
    assert false_negative.decision.status is PolicyDecisionStatus.OBSERVE_ONLY


def test_policy_review_timeout_rejection_and_false_positive_rollback(
    central_simulation_config: SimulationConfig,
) -> None:
    timeout = apply_policy(
        _eligible(),
        hidden_incomplete=True,
        config=central_simulation_config,
        random=SequenceRandom((0.0, 0.9, 0.9, 0.5, 0.0)),
    )
    assert timeout.decision.status is PolicyDecisionStatus.FALLBACK_TO_MANUAL
    rejected = apply_policy(
        _eligible(),
        hidden_incomplete=True,
        config=central_simulation_config,
        random=SequenceRandom((0.0, 0.9, 0.9, 0.5, 0.9, 0.99)),
    )
    assert rejected.decision.status is PolicyDecisionStatus.REJECTED_BY_REVIEWER
    false_positive = apply_policy(
        _eligible(),
        hidden_incomplete=False,
        config=central_simulation_config,
        random=SequenceRandom((0.0, 0.9, 0.0, 0.5, 0.9, 0.0)),
    )
    assert false_positive.decision.status is PolicyDecisionStatus.ROLLED_BACK
    assert "prohibited_external_action_prevented" in false_positive.decision.reason_codes


def test_policy_approval_fallback_and_post_approval_rollback(
    central_simulation_config: SimulationConfig,
) -> None:
    fallback = apply_policy(
        _eligible(),
        hidden_incomplete=True,
        config=central_simulation_config,
        random=SequenceRandom((0.0, 0.9, 0.9, 0.5, 0.9, 0.0, 0.0)),
    )
    assert fallback.decision.status is PolicyDecisionStatus.FALLBACK_TO_MANUAL
    rollback = apply_policy(
        _eligible(),
        hidden_incomplete=True,
        config=central_simulation_config,
        random=SequenceRandom((0.0, 0.9, 0.9, 0.5, 0.9, 0.0, 0.9, 0.0)),
    )
    assert rollback.decision.status is PolicyDecisionStatus.ROLLED_BACK
    approved = apply_policy(
        _eligible(),
        hidden_incomplete=True,
        config=central_simulation_config,
        random=SequenceRandom((0.0, 0.9, 0.9, 0.5, 0.9, 0.0, 0.9, 0.9, 0.0)),
    )
    assert approved.decision.status is PolicyDecisionStatus.APPROVED_SIMULATED_ACTION
