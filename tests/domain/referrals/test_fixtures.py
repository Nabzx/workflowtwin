"""Expectation tests for deterministic fictional referral scenarios."""

from collections import Counter
from itertools import pairwise

from workflowtwin.domain.referrals.enums import EventType, ReferralStatus
from workflowtwin.domain.referrals.fixtures import (
    all_referral_scenarios,
    referral_recategorised_and_reassigned,
    referral_with_delayed_out_of_order_ingestion,
    referral_with_duplicate_source_event,
    referral_with_failed_scheduling_attempts,
    referral_with_repeated_missing_information_requests,
    straight_through_successful_referral,
    stuck_referral,
)


def test_fixture_catalogue_contains_ten_unique_synthetic_cases() -> None:
    scenarios = all_referral_scenarios()

    assert len(scenarios) == 10
    assert len({scenario.name for scenario in scenarios}) == 10
    assert len({scenario.case.id for scenario in scenarios}) == 10
    assert len({scenario.case.external_source_id for scenario in scenarios}) == 10
    assert all(scenario.case.is_synthetic for scenario in scenarios)
    assert all(scenario.case.schema_version == 1 for scenario in scenarios)


def test_fixture_generation_is_reproducible() -> None:
    assert all_referral_scenarios() == all_referral_scenarios()


def test_straight_through_sequence_matches_expected_path() -> None:
    event_types = [event.event_type for event in straight_through_successful_referral().events]

    assert event_types == [
        EventType.REFERRAL_SUBMITTED,
        EventType.REFERRAL_RECEIVED,
        EventType.COMPLETENESS_CHECK_COMPLETED,
        EventType.REFERRAL_CATEGORISED,
        EventType.CLINICAL_TEAM_ASSIGNED,
        EventType.APPOINTMENT_SCHEDULING_STARTED,
        EventType.APPOINTMENT_BOOKED,
        EventType.PATIENT_NOTIFIED,
        EventType.REFERRAL_COMPLETED,
    ]


def test_repeated_information_fixture_has_two_loops_and_three_checks() -> None:
    scenario = referral_with_repeated_missing_information_requests()
    event_counts = Counter(event.event_type for event in scenario.events)

    assert event_counts[EventType.MISSING_INFORMATION_REQUESTED] == 2
    assert event_counts[EventType.MISSING_INFORMATION_RECEIVED] == 2
    assert event_counts[EventType.COMPLETENESS_CHECK_COMPLETED] == 3
    assert scenario.expectation.rework_events == 3


def test_rerouting_fixture_contains_explicit_corrections() -> None:
    scenario = referral_recategorised_and_reassigned()
    event_types = {event.event_type for event in scenario.events}

    assert EventType.REFERRAL_RECATEGORISED in event_types
    assert EventType.CLINICAL_TEAM_REASSIGNED in event_types
    assert scenario.expectation.rework_events == 2


def test_failed_scheduling_fixture_records_each_attempt() -> None:
    scenario = referral_with_failed_scheduling_attempts()
    event_counts = Counter(event.event_type for event in scenario.events)

    assert event_counts[EventType.APPOINTMENT_SCHEDULING_STARTED] == 3
    assert event_counts[EventType.APPOINTMENT_SCHEDULING_FAILED] == 2
    assert scenario.expectation.scheduling_failures == 2


def test_terminal_and_stuck_expectations_match_case_projection() -> None:
    for scenario in all_referral_scenarios():
        if scenario.expectation.terminal_status is not None:
            assert scenario.case.status is scenario.expectation.terminal_status
            assert scenario.case.closed_at is not None

    stuck = stuck_referral()
    assert stuck.case.status is ReferralStatus.AWAITING_INFORMATION
    assert stuck.case.closed_at is None
    assert stuck.expectation.expected_stuck is True


def test_duplicate_scenario_uses_distinct_ids_and_one_source_identity() -> None:
    scenario = referral_with_duplicate_source_event()
    source_id_counts = Counter(event.external_event_id for event in scenario.events)

    assert len({event.id for event in scenario.events}) == len(scenario.events)
    assert [count for count in source_id_counts.values() if count > 1] == [2]
    assert scenario.expectation.contains_duplicate_source_event is True


def test_delayed_event_is_retained_in_ingestion_order() -> None:
    scenario = referral_with_delayed_out_of_order_ingestion()
    ingestion_times = [event.ingested_at for event in scenario.events]
    event_times = [event.event_at for event in scenario.events]

    assert ingestion_times == sorted(ingestion_times)
    assert any(current < previous for previous, current in pairwise(event_times))
    assert scenario.expectation.contains_out_of_order_ingestion is True
