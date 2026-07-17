"""Deterministic case-level eligibility for structured completeness review."""

from workflowtwin.domain.referrals.enums import EventType, ReferralSource
from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent
from workflowtwin.simulation.config import SimulationConfig
from workflowtwin.simulation.models import CaseEligibility, InterventionDefinition


def assess_case_eligibility(
    case: ReferralCase,
    events: tuple[ReferralEvent, ...],
    definition: InterventionDefinition,
    config: SimulationConfig,
) -> CaseEligibility:
    reasons: list[str] = []
    warnings: list[str] = []
    received = tuple(event for event in events if event.event_type is EventType.REFERRAL_RECEIVED)
    checks = tuple(
        event for event in events if event.event_type is EventType.COMPLETENESS_CHECK_COMPLETED
    )
    if case.referral_source is not ReferralSource.GP_PRACTICE:
        reasons.append("outside_gp_practice_cohort")
    if case.schema_version != 1 or any(event.schema_version != 1 for event in events):
        reasons.append("unsupported_schema_version")
    if not received:
        reasons.append("missing_referral_received_event")
    if not checks:
        reasons.append("missing_completeness_check_event")
    if (
        received
        and checks
        and min(check.event_at for check in checks) < min(item.event_at for item in received)
    ):
        reasons.append("unsupported_event_sequence")
    if config.period_start and case.received_at < config.period_start:
        reasons.append("before_simulation_period")
    if config.period_end and case.received_at >= config.period_end:
        reasons.append("after_simulation_period")
    if any(
        event.metadata.get("simulation_intervention_id") == definition.intervention_id
        for event in events
    ):
        reasons.append("duplicate_intervention_attempt")
    if case.status.value in {"completed", "cancelled", "rejected", "closed_other"}:
        warnings.append(
            "historical terminal case is eligible because policy is evaluated at referral receipt"
        )
    return CaseEligibility(
        case_id=case.id,
        eligible=not reasons,
        reason_codes=tuple(reasons) if reasons else ("eligible_structured_admin_case",),
        trigger_event_ids=tuple(event.id for event in received[:1]),
        warnings=tuple(warnings),
    )
