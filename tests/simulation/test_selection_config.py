"""Opportunity selection, intervention definition, and configuration tests."""

import pytest
from pydantic import ValidationError

from workflowtwin.opportunities.models import PortfolioSection
from workflowtwin.simulation.config import SCENARIOS, ScenarioId, SimulationConfig
from workflowtwin.simulation.interventions import define_intervention
from workflowtwin.simulation.models import SimulationInput
from workflowtwin.simulation.selection import (
    select_controlled_prototype,
    validate_selected_opportunity,
)


def test_selects_only_controlled_prototype(
    demo_simulation_input: SimulationInput,
) -> None:
    candidate = select_controlled_prototype(demo_simulation_input.opportunities)

    assert candidate.opportunity_id == "opportunity-7def8c82e8b589e5"
    assert candidate.portfolio_section is PortfolioSection.CONTROLLED_PROTOTYPE
    assert candidate.cohort_value == "gp_practice"


def test_selection_fallback_prefers_lower_risk_then_stable_id(
    demo_simulation_input: SimulationInput,
) -> None:
    analysis = demo_simulation_input.opportunities
    selected = select_controlled_prototype(analysis)
    duplicate = selected.model_copy(
        update={
            "opportunity_id": "opportunity-0000000000000000",
            "risk": selected.risk.model_copy(update={"score": selected.risk.score - 1}),
        }
    )
    expanded = analysis.model_copy(update={"candidates": (*analysis.candidates, duplicate)})

    assert select_controlled_prototype(expanded).opportunity_id == duplicate.opportunity_id


def test_discovery_only_portfolio_is_rejected(
    demo_simulation_input: SimulationInput,
) -> None:
    analysis = demo_simulation_input.opportunities
    candidates = tuple(
        item.model_copy(update={"portfolio_section": PortfolioSection.FURTHER_DISCOVERY})
        for item in analysis.candidates
    )
    with pytest.raises(ValueError, match="no controlled-prototype"):
        select_controlled_prototype(analysis.model_copy(update={"candidates": candidates}))


def test_selected_identifier_must_match_portfolio(
    demo_simulation_input: SimulationInput,
) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        validate_selected_opportunity(demo_simulation_input.opportunities, "opportunity-wrong")


def test_intervention_is_bounded_and_clinical_actions_are_prohibited(
    demo_simulation_input: SimulationInput,
) -> None:
    definition = define_intervention(
        select_controlled_prototype(demo_simulation_input.opportunities)
    )

    assert definition.human_review_required
    assert "no autonomous external communication" in definition.prohibited_actions
    assert any("clinical" in item for item in definition.prohibited_actions)
    assert definition.definition_fingerprint


def test_scenario_presets_are_distinct_and_not_perfect() -> None:
    assert set(SCENARIOS) == set(ScenarioId)
    assert len({item.model_dump_json() for item in SCENARIOS.values()}) == 4
    assert SCENARIOS[ScenarioId.OPTIMISTIC].effectiveness < 1
    assert SCENARIOS[ScenarioId.OPTIMISTIC].intervention_failure_rate > 0


def test_config_rejects_invalid_ranges_and_policy(
    central_simulation_config: SimulationConfig,
) -> None:
    with pytest.raises(ValidationError, match=r"less than or equal"):
        type(central_simulation_config.parameters).model_validate(
            {**central_simulation_config.parameters.model_dump(), "rollout_percentage": 2.0}
        )
    with pytest.raises(ValidationError, match="unsupported intervention"):
        SimulationConfig.model_validate(
            {
                **central_simulation_config.model_dump(),
                "intervention_definition_version": "2.0.0",
            }
        )
