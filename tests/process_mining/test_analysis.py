"""End-to-end fixture semantics for discovery and conformance."""

from datetime import UTC, datetime
from pathlib import Path

from workflowtwin.domain.referrals.fixtures import (
    all_referral_scenarios,
    straight_through_successful_referral,
)
from workflowtwin.process_mining.analyzer import ProcessMiningAnalyzer
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import (
    ConformanceStatus,
    DeviationCategory,
    ProcessAnalysisInput,
)

from .conftest import input_for_scenarios


def test_fixture_processes_reconstruct_and_conform_as_documented() -> None:
    scenarios = all_referral_scenarios()
    process_input = input_for_scenarios(scenarios)
    bundle = ProcessMiningAnalyzer(
        ProcessMiningConfig(
            source_dataset_fingerprint=process_input.dataset_fingerprint,
            minimum_variant_frequency=1,
            rare_variant_case_threshold=1,
            minimum_transition_frequency=1,
            minimum_cohort_size=2,
        )
    ).analyze(
        ProcessAnalysisInput(operational=process_input),
        analysed_at=datetime(2026, 7, 17, tzinfo=UTC),
    )
    by_name = {
        scenario.name: next(
            result for result in bundle.case_results if result.case_id == scenario.case.id
        )
        for scenario in scenarios
    }

    straight = by_name["straight_through_successful_referral"]
    assert straight.strict_conformance is not None
    assert straight.governed_conformance is not None
    assert straight.strict_conformance.status is ConformanceStatus.FULLY_CONFORMING
    assert straight.governed_conformance.status is ConformanceStatus.FULLY_CONFORMING
    assert not straight.strict_conformance.deviations

    missing = by_name["referral_missing_information_once"]
    assert missing.strict_conformance is not None
    assert missing.governed_conformance is not None
    assert missing.strict_conformance.status is ConformanceStatus.PARTIALLY_CONFORMING
    assert missing.governed_conformance.status is ConformanceStatus.FULLY_CONFORMING

    repeated = by_name["referral_with_repeated_missing_information_requests"]
    assert repeated.governed_conformance is not None
    assert DeviationCategory.EXCESSIVE_LOOP in {
        item.category for item in repeated.governed_conformance.deviations
    }

    scheduling = by_name["referral_with_failed_scheduling_attempts"]
    assert scheduling.governed_conformance is not None
    assert DeviationCategory.SCHEDULING_RETRY in {
        item.category for item in scheduling.governed_conformance.deviations
    }

    stuck = by_name["stuck_referral"]
    assert stuck.governed_conformance is not None
    assert DeviationCategory.MISSING_TERMINAL in {
        item.category for item in stuck.governed_conformance.deviations
    }

    cancelled = by_name["cancelled_referral"]
    rejected = by_name["rejected_referral"]
    assert cancelled.governed_conformance is not None
    assert rejected.governed_conformance is not None
    assert cancelled.governed_conformance.status is ConformanceStatus.FULLY_CONFORMING
    assert rejected.governed_conformance.status is ConformanceStatus.FULLY_CONFORMING

    analysis = bundle.analysis
    assert analysis.discovery.discovered
    assert analysis.discovery.pm4py_dfg_matches_canonical
    assert sum(variant.case_count for variant in analysis.variants) == len(scenarios)
    assert sum(analysis.start_activity_counts.values()) == len(scenarios)
    assert sum(analysis.end_activity_counts.values()) == len(scenarios)
    assert len(analysis.graph_data.edges) == len(analysis.transition_statistics)


def test_optional_svg_export_produces_reference_and_discovery_models(tmp_path: Path) -> None:
    process_input = input_for_scenarios((straight_through_successful_referral(),))
    visualisations = tmp_path / "visualisations"

    bundle = ProcessMiningAnalyzer(
        ProcessMiningConfig(
            source_dataset_fingerprint=process_input.dataset_fingerprint,
            minimum_cohort_size=2,
            visualisation_directory=visualisations,
        )
    ).analyze(ProcessAnalysisInput(operational=process_input))

    expected_names = {
        "frequency-dfg.svg",
        "performance-dfg.svg",
        "discovered-process-tree.svg",
        "discovered-petri-net.svg",
        "northstar-strict-v1.svg",
        "northstar-governed-v1.svg",
    }
    rendered_names = {path.name for path in visualisations.glob("*.svg")}
    if bundle.visualisation_warnings:
        assert len(bundle.visualisation_warnings) == 6
        assert not rendered_names
        assert all("unavailable" in warning for warning in bundle.visualisation_warnings)
    else:
        assert rendered_names == expected_names
        assert {Path(path).name for path in bundle.analysis.visualisation_artifacts} == (
            expected_names
        )
