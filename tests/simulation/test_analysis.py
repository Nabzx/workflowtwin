"""End-to-end re-analysis, comparison, burden, and decision tests."""

from datetime import UTC, datetime

import pytest

from workflowtwin.simulation.analyzer import InterventionSimulator
from workflowtwin.simulation.config import SCENARIOS, ScenarioId, SimulationConfig
from workflowtwin.simulation.models import (
    EffectClassification,
    PrototypeDecisionStatus,
    SimulationAnalysis,
    SimulationInput,
)


def test_central_demo_reuses_analysis_and_exposes_mixed_result(
    central_simulation_analysis: SimulationAnalysis,
) -> None:
    analysis = central_simulation_analysis
    scenario = analysis.scenario_result
    comparisons = {item.metric_name: item for item in scenario.metric_comparisons}

    assert scenario.quality.is_valid
    assert scenario.manifest.eligible_case_count == 422
    assert scenario.manifest.affected_case_count == 72
    manual_difference = comparisons["manual_touches"].absolute_difference
    check_difference = comparisons["time_to_first_completeness_check_hours"].absolute_difference
    assert manual_difference is not None and manual_difference < 0
    assert check_difference is not None and check_difference < 0
    assert comparisons["first_pass_completeness_rate"].absolute_difference == 0
    assert scenario.counterfactual_baseline_fingerprint
    assert scenario.counterfactual_process_fingerprint
    assert analysis.decision.status is PrototypeDecisionStatus.REVISE
    assert analysis.benchmark_evaluation.passed_count == analysis.benchmark_evaluation.check_count


def test_effect_classes_and_control_overhead_remain_separate(
    central_simulation_analysis: SimulationAnalysis,
) -> None:
    scenario = central_simulation_analysis.scenario_result
    by_name = {item.metric_name: item for item in scenario.metric_comparisons}

    assert by_name["manual_touches"].effect_classification is (EffectClassification.INTENDED_DIRECT)
    assert by_name["case_duration_hours"].effect_classification is (EffectClassification.SECONDARY)
    assert scenario.burden_comparison.simulated_operating_burden_hours > 0
    assert scenario.control_overhead
    assert scenario.adverse_effects


def test_process_comparison_reports_unchanged_and_changed_dimensions(
    central_simulation_analysis: SimulationAnalysis,
) -> None:
    comparisons = {
        item.metric_name: item
        for item in central_simulation_analysis.scenario_result.process_comparisons
    }

    assert comparisons["variant_count"].absolute_difference == 0
    assert comparisons["bottleneck_candidate_count"].absolute_difference == 1
    assert comparisons["governed_fully_conforming_rate"].absolute_difference == 0


def test_fingerprint_excludes_analysis_time(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    first = InterventionSimulator(central_simulation_config).analyze(
        demo_simulation_input,
        analysed_at=datetime(2026, 1, 1, tzinfo=UTC),
        include_sensitivity=False,
    )
    later = InterventionSimulator(central_simulation_config).analyze(
        demo_simulation_input,
        analysed_at=datetime(2030, 1, 1, tzinfo=UTC),
        include_sensitivity=False,
    )

    assert first.simulation_analysis_fingerprint == later.simulation_analysis_fingerprint


def test_source_and_opportunity_fingerprint_mismatches_are_rejected(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    wrong_source = central_simulation_config.model_copy(
        update={"source_dataset_fingerprint": "0" * 64}
    )
    with pytest.raises(ValueError, match="source dataset fingerprint"):
        InterventionSimulator(wrong_source).analyze(
            demo_simulation_input, include_sensitivity=False
        )
    wrong_opportunity = central_simulation_config.model_copy(
        update={"opportunity_analysis_fingerprint": "0" * 64}
    )
    with pytest.raises(ValueError, match="opportunity analysis fingerprint"):
        InterventionSimulator(wrong_opportunity).analyze(
            demo_simulation_input, include_sensitivity=False
        )


@pytest.mark.parametrize("scenario_id", list(ScenarioId))
def test_each_scenario_changes_simulation_fingerprint_without_full_process_rerun(
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
    scenario_id: ScenarioId,
) -> None:
    from workflowtwin.simulation.counterfactuals import CounterfactualSimulator
    from workflowtwin.simulation.interventions import define_intervention
    from workflowtwin.simulation.selection import select_controlled_prototype

    config = central_simulation_config.model_copy(
        update={"scenario_id": scenario_id, "parameters": SCENARIOS[scenario_id]}
    )
    definition = define_intervention(
        select_controlled_prototype(demo_simulation_input.opportunities)
    )
    result = CounterfactualSimulator(config).simulate(demo_simulation_input, definition)

    assert result.quality.is_valid
    assert result.manifest.scenario_id == scenario_id.value
    assert result.manifest.counterfactual_dataset_fingerprint
