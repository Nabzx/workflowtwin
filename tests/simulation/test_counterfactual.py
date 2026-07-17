"""Counterfactual provenance, determinism, validation, and isolation tests."""

from dataclasses import replace

from workflowtwin.analytics.fingerprint import dataset_fingerprint
from workflowtwin.analytics.models import AnalysisInput
from workflowtwin.simulation.config import SimulationConfig
from workflowtwin.simulation.counterfactuals import CounterfactualSimulator
from workflowtwin.simulation.interventions import define_intervention
from workflowtwin.simulation.models import (
    CounterfactualResult,
    PolicyDecisionStatus,
    SimulationInput,
)
from workflowtwin.simulation.selection import select_controlled_prototype


def _simulate(simulation_input: SimulationInput, config: SimulationConfig) -> CounterfactualResult:
    candidate = select_controlled_prototype(simulation_input.opportunities)
    return CounterfactualSimulator(config).simulate(
        simulation_input, define_intervention(candidate)
    )


def test_source_events_remain_unchanged_and_changes_have_provenance(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    before = dataset_fingerprint(
        demo_simulation_input.source.cases, demo_simulation_input.source.events
    )
    result = _simulate(demo_simulation_input, central_simulation_config)
    after = dataset_fingerprint(
        demo_simulation_input.source.cases, demo_simulation_input.source.events
    )

    assert before == after
    assert result.quality.is_valid
    assert result.quality.source_events_unchanged
    changes = tuple(change for case in result.case_results for change in case.event_changes)
    assert changes
    assert all(change.provenance for change in changes)
    assert all(change.original_event is not None for change in changes)
    assert all(change.counterfactual_event is not None for change in changes)
    assert all(change.source_event_id != change.counterfactual_event_id for change in changes)


def test_same_seed_is_stable_and_different_seed_changes_outcomes(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    first = _simulate(demo_simulation_input, central_simulation_config)
    repeated = _simulate(demo_simulation_input, central_simulation_config)
    changed = _simulate(
        demo_simulation_input,
        central_simulation_config.model_copy(update={"simulation_seed": 99}),
    )

    assert first.manifest == repeated.manifest
    assert first.case_results == repeated.case_results
    assert first.manifest.counterfactual_dataset_fingerprint != (
        changed.manifest.counterfactual_dataset_fingerprint
    )


def test_case_iteration_order_does_not_change_logical_output(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    source = demo_simulation_input.source
    reversed_source = AnalysisInput(
        cases=tuple(reversed(source.cases)),
        events=tuple(reversed(source.events)),
        dataset_fingerprint=source.dataset_fingerprint,
        generation_run_id=source.generation_run_id,
        manifest=source.manifest,
        ground_truth=None,
    )
    reversed_input = replace(demo_simulation_input, source=reversed_source)

    normal = _simulate(demo_simulation_input, central_simulation_config)
    reordered = _simulate(reversed_input, central_simulation_config)

    assert normal.manifest == reordered.manifest
    assert normal.case_results == reordered.case_results


def test_only_eligible_approved_cases_receive_event_changes(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    result = _simulate(demo_simulation_input, central_simulation_config)

    for case in result.case_results:
        if case.event_changes:
            assert case.eligibility.eligible
            assert case.decision.status is PolicyDecisionStatus.APPROVED_SIMULATED_ACTION
        else:
            assert case.decision.status is not PolicyDecisionStatus.APPROVED_SIMULATED_ACTION


def test_ground_truth_is_not_required_for_counterfactual_policy(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    with_truth = _simulate(demo_simulation_input, central_simulation_config)
    without_truth = _simulate(
        replace(demo_simulation_input, ground_truth=None), central_simulation_config
    )

    assert with_truth.manifest == without_truth.manifest
    assert with_truth.case_results == without_truth.case_results


def test_maximum_affected_case_count_is_a_hard_policy_cap(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    result = _simulate(
        demo_simulation_input,
        central_simulation_config.model_copy(update={"maximum_affected_case_count": 2}),
    )

    assert result.manifest.affected_case_count == 2
    assert any(
        case.decision.status is PolicyDecisionStatus.BLOCKED_POLICY for case in result.case_results
    )
