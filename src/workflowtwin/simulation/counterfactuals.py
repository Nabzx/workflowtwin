"""Immutable counterfactual event overlays for the completeness intervention."""

from collections import Counter, defaultdict
from datetime import timedelta
from random import Random
from uuid import UUID

from workflowtwin.analytics.fingerprint import dataset_fingerprint
from workflowtwin.analytics.models import AnalysisInput
from workflowtwin.domain.referrals.enums import (
    ActorType,
    CommunicationChannel,
    EventType,
    SourceSystem,
)
from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent
from workflowtwin.simulation.config import SimulationConfig
from workflowtwin.simulation.eligibility import assess_case_eligibility
from workflowtwin.simulation.fingerprint import (
    case_random_seed,
    counterfactual_event_id,
    stable_id,
)
from workflowtwin.simulation.models import (
    CaseSimulationResult,
    CounterfactualResult,
    EventChange,
    EventChangeType,
    InterventionDefinition,
    PolicyDecisionStatus,
    SimulationInput,
    SimulationManifest,
)
from workflowtwin.simulation.policy import PolicyOutcome, apply_policy
from workflowtwin.simulation.validation import validate_counterfactual

FICTIONAL_COUNTERFACTUAL_DECLARATION = (
    "Northstar Clinics, all records, intervention decisions, and effects are fictional and "
    "counterfactual; no production automation or realised impact exists."
)


def _replace_event(
    event: ReferralEvent,
    *,
    simulation_run_id: str,
    rule: str,
    event_at_shift_hours: float = 0.0,
    manual: bool | None = None,
    system_actor: bool = False,
) -> ReferralEvent:
    identifier = counterfactual_event_id(
        simulation_run_id=simulation_run_id, source_event_id=event.id, rule=rule
    )
    return event.model_copy(
        update={
            "id": identifier,
            "external_event_id": f"SIM-{identifier.hex.upper()}",
            "event_at": event.event_at + timedelta(hours=event_at_shift_hours),
            "actor_type": ActorType.SYSTEM if system_actor else event.actor_type,
            "actor_identifier": None if system_actor else event.actor_identifier,
            "source_system": SourceSystem.ADMIN_SYSTEM if system_actor else event.source_system,
            "channel": (CommunicationChannel.INTERNAL_SYSTEM if system_actor else event.channel),
            "requires_manual_work": (event.requires_manual_work if manual is None else manual),
            "metadata": {
                **event.metadata,
                "simulation_intervention_id": "northstar-structured-completeness-review",
                "simulation_rule": rule,
                "source_event_id": str(event.id),
            },
        }
    )


def _event_change(
    original: ReferralEvent,
    counterfactual: ReferralEvent,
    *,
    simulation_run_id: str,
    intervention_id: str,
    rule: str,
    human_review_action: str,
) -> EventChange:
    changes = [EventChangeType.REPLACED]
    adjustment = (counterfactual.event_at - original.event_at).total_seconds() / 3600
    if adjustment:
        changes.append(EventChangeType.TIMESTAMP_SHIFTED)
    if counterfactual.requires_manual_work != original.requires_manual_work:
        changes.append(EventChangeType.MANUAL_MARKER_CHANGED)
    if counterfactual.actor_type != original.actor_type:
        changes.append(EventChangeType.ACTOR_TYPE_CHANGED)
    return EventChange(
        change_id=stable_id(
            "change",
            {
                "run": simulation_run_id,
                "source": str(original.id),
                "counterfactual": str(counterfactual.id),
                "rule": rule,
            },
        ),
        simulation_run_id=simulation_run_id,
        intervention_id=intervention_id,
        case_id=original.referral_case_id,
        source_event_id=original.id,
        counterfactual_event_id=counterfactual.id,
        change_types=tuple(changes),
        original_event=original,
        counterfactual_event=counterfactual,
        causal_simulation_rule=rule,
        event_time_adjustment_hours=adjustment,
        ingestion_time_treatment="source ingestion timestamp retained as provenance",
        human_review_action=human_review_action,
        warnings=("counterfactual timing is assumption-dependent",),
        provenance=(
            f"source_event:{original.id}",
            f"simulation_run:{simulation_run_id}",
            "human_approval_required",
        ),
    )


def _transform_incomplete_path(
    events: tuple[ReferralEvent, ...],
    outcome: PolicyOutcome,
    definition: InterventionDefinition,
    config: SimulationConfig,
    random: Random,
    simulation_run_id: str,
) -> tuple[tuple[ReferralEvent, ...], tuple[EventChange, ...]]:
    first_received = next(
        event for event in events if event.event_type is EventType.REFERRAL_RECEIVED
    )
    first_check = next(
        event for event in events if event.event_type is EventType.COMPLETENESS_CHECK_COMPLETED
    )
    first_request = next(
        event for event in events if event.event_type is EventType.MISSING_INFORMATION_REQUESTED
    )
    review_hours = outcome.decision.review_turnaround_hours or 0.0
    system_hours = random.uniform(*config.parameters.system_processing_delay_hours)
    check_target = first_received.event_at + timedelta(hours=review_hours + system_hours)
    request_target = check_target + timedelta(hours=system_hours)
    request_shift = (request_target - first_request.event_at).total_seconds() / 3600
    check_shift = (check_target - first_check.event_at).total_seconds() / 3600

    transformed: list[ReferralEvent] = []
    changes: list[EventChange] = []
    request_seen = False
    for event in events:
        replacement: ReferralEvent | None = None
        rule = ""
        if event.id == first_check.id:
            rule = "approved_structured_first_completeness_validation"
            replacement = _replace_event(
                event,
                simulation_run_id=simulation_run_id,
                rule=rule,
                event_at_shift_hours=check_shift,
                manual=False,
                system_actor=True,
            )
        elif event.id == first_request.id:
            request_seen = True
            rule = "human_approved_earlier_staff_information_request"
            replacement = _replace_event(
                event,
                simulation_run_id=simulation_run_id,
                rule=rule,
                event_at_shift_hours=request_shift,
            )
        elif request_seen:
            rule = "preserve_downstream_interval_after_approved_request"
            is_recheck = event.event_type is EventType.COMPLETENESS_CHECK_COMPLETED
            replacement = _replace_event(
                event,
                simulation_run_id=simulation_run_id,
                rule=rule,
                event_at_shift_hours=request_shift,
                manual=False if is_recheck and outcome.effective_action else None,
                system_actor=is_recheck and outcome.effective_action,
            )
        if replacement is None:
            transformed.append(event)
            continue
        transformed.append(replacement)
        changes.append(
            _event_change(
                event,
                replacement,
                simulation_run_id=simulation_run_id,
                intervention_id=definition.intervention_id,
                rule=rule,
                human_review_action="approved_by_referral_administrator",
            )
        )
    return tuple(transformed), tuple(changes)


def _update_case_projection(case: ReferralCase, events: tuple[ReferralEvent, ...]) -> ReferralCase:
    terminal_types = {
        EventType.REFERRAL_COMPLETED,
        EventType.REFERRAL_CANCELLED,
        EventType.REFERRAL_REJECTED,
        EventType.REFERRAL_CLOSED_OTHER,
    }
    terminal = next((event for event in events if event.event_type in terminal_types), None)
    if terminal is None:
        return case
    return case.model_copy(
        update={
            "closed_at": terminal.event_at,
            "updated_at": max(case.created_at, terminal.event_at),
        }
    )


class CounterfactualSimulator:
    """Apply one guarded intervention without mutating operational source facts."""

    def __init__(self, config: SimulationConfig) -> None:
        self._config = config

    def simulate(
        self,
        simulation_input: SimulationInput,
        definition: InterventionDefinition,
    ) -> CounterfactualResult:
        source = simulation_input.source
        if dataset_fingerprint(source.cases, source.events) != source.dataset_fingerprint:
            raise ValueError("source records do not match the configured dataset fingerprint")
        simulation_run_id = stable_id(
            "simulation-run",
            {
                "simulation_id": self._config.simulation_id,
                "scenario": self._config.scenario_id.value,
                "seed": self._config.simulation_seed,
                "source": source.dataset_fingerprint,
                "intervention": definition.definition_fingerprint,
                "parameters": self._config.parameters,
            },
        )
        events_by_case: dict[UUID, list[ReferralEvent]] = defaultdict(list)
        for event in source.events:
            events_by_case[event.referral_case_id].append(event)

        case_results: list[CaseSimulationResult] = []
        counterfactual_cases: list[ReferralCase] = []
        counterfactual_events: list[ReferralEvent] = []
        affected_count = 0
        for case in sorted(source.cases, key=lambda item: item.id.hex):
            events = tuple(
                sorted(events_by_case[case.id], key=lambda item: (item.event_at, item.id.hex))
            )
            eligibility = assess_case_eligibility(case, events, definition, self._config)
            hidden_incomplete = any(
                event.event_type is EventType.MISSING_INFORMATION_REQUESTED for event in events
            )
            random = Random(
                case_random_seed(
                    simulation_seed=self._config.simulation_seed,
                    case_id=case.id,
                    intervention_version=definition.intervention_version,
                    scenario_id=self._config.scenario_id.value,
                )
            )
            outcome = apply_policy(
                eligibility,
                hidden_incomplete=hidden_incomplete,
                config=self._config,
                random=random,
            )
            if (
                outcome.decision.status is PolicyDecisionStatus.APPROVED_SIMULATED_ACTION
                and affected_count >= self._config.maximum_affected_case_count
            ):
                outcome = PolicyOutcome(
                    decision=outcome.decision.model_copy(
                        update={
                            "status": PolicyDecisionStatus.BLOCKED_POLICY,
                            "reason_codes": ("maximum_affected_case_count_reached",),
                            "simulated_action": None,
                            "manual_touch_overhead": 0.0,
                        }
                    ),
                    detector_outcome=outcome.detector_outcome,
                    effective_action=False,
                )
            if outcome.decision.status is PolicyDecisionStatus.APPROVED_SIMULATED_ACTION:
                transformed, changes = _transform_incomplete_path(
                    events,
                    outcome,
                    definition,
                    self._config,
                    random,
                    simulation_run_id,
                )
                affected_count += 1
            else:
                transformed, changes = events, ()
            counterfactual_cases.append(_update_case_projection(case, transformed))
            counterfactual_events.extend(transformed)
            case_results.append(
                CaseSimulationResult(
                    case_id=case.id,
                    eligibility=eligibility,
                    decision=outcome.decision,
                    hidden_simulation_truth=(
                        "historical_missing_information_path"
                        if hidden_incomplete
                        else "historical_first_pass_complete_path"
                    ),
                    detector_outcome=outcome.detector_outcome,
                    event_changes=changes,
                )
            )

        ordered_cases = tuple(sorted(counterfactual_cases, key=lambda item: item.id.hex))
        ordered_events = tuple(
            sorted(
                counterfactual_events,
                key=lambda item: (item.referral_case_id.hex, item.event_at, item.id.hex),
            )
        )
        counterfactual_fingerprint = dataset_fingerprint(ordered_cases, ordered_events)
        operational = AnalysisInput(
            cases=ordered_cases,
            events=ordered_events,
            dataset_fingerprint=counterfactual_fingerprint,
            generation_run_id=source.generation_run_id,
            manifest=None,
            ground_truth=None,
        )
        quality = validate_counterfactual(
            source=source,
            counterfactual=operational,
            case_results=tuple(case_results),
        )
        manifest = self._manifest(
            simulation_run_id,
            source,
            tuple(case_results),
            definition,
            counterfactual_fingerprint,
            len(ordered_events),
        )
        return CounterfactualResult(
            operational=operational,
            case_results=tuple(case_results),
            quality=quality,
            manifest=manifest,
        )

    def _manifest(
        self,
        simulation_run_id: str,
        source: AnalysisInput,
        results: tuple[CaseSimulationResult, ...],
        definition: InterventionDefinition,
        counterfactual_fingerprint: str,
        counterfactual_event_count: int,
    ) -> SimulationManifest:
        statuses = Counter(item.decision.status.value for item in results)
        changes = Counter(
            change_type.value
            for result in results
            for change in result.event_changes
            for change_type in change.change_types
        )
        detector = Counter(item.detector_outcome for item in results)
        eligible = sum(item.eligibility.eligible for item in results)
        reviewed = sum(item.decision.review_turnaround_hours is not None for item in results)
        config = self._config.model_dump(mode="json")
        for field in ("analysis_output", "report_output", "comparison_output", "case_output"):
            config.pop(field, None)
        parameters = self._config.parameters
        return SimulationManifest(
            simulation_version=self._config.simulation_version,
            simulation_id=self._config.simulation_id,
            simulation_run_id=simulation_run_id,
            scenario_id=self._config.scenario_id.value,
            source_dataset_fingerprint=source.dataset_fingerprint,
            baseline_analysis_fingerprint=self._config.baseline_analysis_fingerprint,
            process_analysis_fingerprint=self._config.process_analysis_fingerprint,
            opportunity_analysis_fingerprint=self._config.opportunity_analysis_fingerprint,
            selected_opportunity_id=self._config.selected_opportunity_id,
            intervention_id=definition.intervention_id,
            intervention_version=definition.intervention_version,
            policy_version=self._config.policy_version,
            seed=self._config.simulation_seed,
            configuration=config,
            source_case_count=len(source.cases),
            source_event_count=len(source.events),
            eligible_case_count=eligible,
            excluded_case_count=len(results) - eligible,
            affected_case_count=statuses[PolicyDecisionStatus.APPROVED_SIMULATED_ACTION.value],
            observe_only_count=statuses[PolicyDecisionStatus.OBSERVE_ONLY.value],
            review_required_count=reviewed,
            approved_action_count=statuses[PolicyDecisionStatus.APPROVED_SIMULATED_ACTION.value],
            rejected_action_count=statuses[PolicyDecisionStatus.REJECTED_BY_REVIEWER.value],
            intervention_failure_count=statuses[PolicyDecisionStatus.SIMULATION_FAILURE.value],
            fallback_count=statuses[PolicyDecisionStatus.FALLBACK_TO_MANUAL.value]
            + statuses[PolicyDecisionStatus.SIMULATION_FAILURE.value],
            rollback_count=statuses[PolicyDecisionStatus.ROLLED_BACK.value],
            counterfactual_case_count=len(results),
            counterfactual_event_count=counterfactual_event_count,
            change_type_counts=dict(sorted(changes.items())),
            configured_rates={
                "rollout_percentage": parameters.rollout_percentage,
                "effectiveness": parameters.effectiveness,
                "false_positive_rate": parameters.false_positive_rate,
                "false_negative_rate": parameters.false_negative_rate,
                "review_acceptance_rate": parameters.human_review_acceptance_rate,
                "manual_fallback_rate": parameters.manual_fallback_rate,
                "intervention_failure_rate": parameters.intervention_failure_rate,
            },
            realised_rates={
                "false_positive_rate": detector["false_positive"] / eligible if eligible else None,
                "false_negative_rate": detector["false_negative"] / eligible if eligible else None,
                "review_rate": reviewed / eligible if eligible else None,
                "affected_rate": (
                    statuses[PolicyDecisionStatus.APPROVED_SIMULATED_ACTION.value] / eligible
                    if eligible
                    else None
                ),
            },
            assumptions=(
                "historical event paths are used only as a simulation oracle",
                "configured probabilities are assumptions; realised counts are reported separately",
            ),
            warnings=("simulation results require prospective shadow-mode validation",),
            counterfactual_dataset_fingerprint=counterfactual_fingerprint,
            fictional_counterfactual_declaration=FICTIONAL_COUNTERFACTUAL_DECLARATION,
        )
