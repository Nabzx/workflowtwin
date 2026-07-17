"""Canonical activity mapping, ordering, and source-retry tests."""

import pytest

from workflowtwin.analytics.models import AnalysisInput
from workflowtwin.domain.referrals.fixtures import (
    referral_missing_information_once,
    referral_recategorised_and_reassigned,
    referral_with_delayed_out_of_order_ingestion,
    referral_with_duplicate_source_event,
    referral_with_failed_scheduling_attempts,
    referral_with_repeated_missing_information_requests,
    straight_through_successful_referral,
)
from workflowtwin.process_mining.activity_mapping import (
    ACTIVITY_BY_EVENT_TYPE,
    ACTIVITY_MAPPING_VERSION,
)
from workflowtwin.process_mining.analyzer import ProcessMiningAnalyzer
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.event_log import build_process_log
from workflowtwin.process_mining.models import ProcessAnalysisInput

from .conftest import input_for_scenarios


def test_activity_mapping_is_complete_and_versioned() -> None:
    assert ACTIVITY_MAPPING_VERSION == "northstar-activity-map-v1"
    assert len(ACTIVITY_BY_EVENT_TYPE) == 18
    assert len(set(ACTIVITY_BY_EVENT_TYPE.values())) == 18


def test_straight_through_sequence_is_deterministic() -> None:
    scenario = straight_through_successful_referral()
    process_log = build_process_log(
        input_for_scenarios((scenario,)), ProcessMiningConfig(minimum_cohort_size=2)
    )

    assert process_log.traces[0].activities == (
        "Referral submitted",
        "Referral received",
        "Completeness checked",
        "Referral categorised",
        "Clinical team assigned",
        "Scheduling started",
        "Appointment booked",
        "Patient notified",
        "Referral completed",
    )
    assert process_log.quality.events_included == 9


@pytest.mark.parametrize(
    ("scenario_factory", "expected"),
    [
        (
            referral_missing_information_once,
            ("Missing information requested", "Missing information received"),
        ),
        (
            referral_with_repeated_missing_information_requests,
            ("Missing information requested", "Missing information requested"),
        ),
        (
            referral_recategorised_and_reassigned,
            ("Referral recategorised", "Clinical team reassigned"),
        ),
        (
            referral_with_failed_scheduling_attempts,
            ("Scheduling failed", "Scheduling failed"),
        ),
    ],
)
def test_exception_activities_are_preserved(
    scenario_factory: object, expected: tuple[str, str]
) -> None:
    scenario = scenario_factory()  # type: ignore[operator]
    process_log = build_process_log(
        input_for_scenarios((scenario,)), ProcessMiningConfig(minimum_cohort_size=2)
    )
    activities = process_log.traces[0].activities

    for activity in expected:
        assert activity in activities
    if expected[0] == expected[1]:
        assert activities.count(expected[0]) == 2


def test_delayed_ingestion_does_not_change_event_time_order() -> None:
    scenario = referral_with_delayed_out_of_order_ingestion()
    process_log = build_process_log(
        input_for_scenarios((scenario,)), ProcessMiningConfig(minimum_cohort_size=2)
    )

    assert process_log.traces[0].activities.index("Referral categorised") < (
        process_log.traces[0].activities.index("Clinical team assigned")
    )
    assert process_log.quality.out_of_order_ingestion_cases == 1
    assert "ingestion order differs from event-time order" in process_log.quality.warnings


def test_duplicate_source_attempt_does_not_add_a_process_step() -> None:
    scenario = referral_with_duplicate_source_event()
    process_log = build_process_log(
        input_for_scenarios((scenario,)), ProcessMiningConfig(minimum_cohort_size=2)
    )

    assert process_log.traces[0].activities.count("Referral received") == 1
    assert process_log.quality.duplicate_events_excluded == 1


def test_source_fingerprint_is_required_to_match() -> None:
    scenario = straight_through_successful_referral()
    operational = input_for_scenarios((scenario,))
    invalid = AnalysisInput(
        cases=operational.cases,
        events=operational.events,
        dataset_fingerprint="0" * 64,
        generation_run_id=None,
        manifest=None,
        ground_truth=None,
    )

    with pytest.raises(ValueError, match="fingerprint"):
        ProcessMiningAnalyzer(ProcessMiningConfig(minimum_cohort_size=2)).analyze(
            ProcessAnalysisInput(operational=invalid)
        )
