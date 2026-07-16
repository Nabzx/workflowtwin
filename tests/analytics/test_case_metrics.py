"""Exact case-metric assertions over the deterministic referral catalogue."""

from datetime import UTC, datetime

import pytest

from workflowtwin.analytics.case_metrics import calculate_case_metrics
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.models import CaseMetrics, MetricName, MetricStatus
from workflowtwin.analytics.timelines import build_timelines
from workflowtwin.domain.referrals.fixtures import (
    ReferralScenario,
    cancelled_referral,
    referral_missing_information_once,
    referral_recategorised_and_reassigned,
    referral_with_delayed_out_of_order_ingestion,
    referral_with_duplicate_source_event,
    referral_with_failed_scheduling_attempts,
    referral_with_repeated_missing_information_requests,
    rejected_referral,
    straight_through_successful_referral,
    stuck_referral,
)


def _metrics(scenario: ReferralScenario, config: AnalysisConfig | None = None) -> CaseMetrics:
    selected_config = config or AnalysisConfig()
    timeline = build_timelines((scenario.case,), scenario.events, selected_config).timelines[0]
    return calculate_case_metrics(timeline, selected_config)


def test_straight_through_metrics_have_exact_boundaries_and_provenance() -> None:
    metrics = _metrics(straight_through_successful_referral())

    assert metrics.lifecycle_status == "completed"
    assert metrics.metrics[MetricName.CASE_DURATION].value == 8
    assert metrics.metrics[MetricName.FIRST_PASS_COMPLETE].value is True
    assert metrics.metrics[MetricName.REWORK_COUNT].value == 0
    assert metrics.metrics[MetricName.MANUAL_TOUCHES].value == 6
    assert metrics.metrics[MetricName.HANDOFFS].value == 2
    assert metrics.metrics[MetricName.TIME_TO_BOOKING].value == 7
    assert len(metrics.metrics[MetricName.CASE_DURATION].source_event_ids) == 2


@pytest.mark.parametrize(
    ("scenario", "duration", "waiting", "touches", "rework"),
    [
        (referral_missing_information_once(), 33, 12.5, 8, 1),
        (referral_with_repeated_missing_information_requests(), 60, 23, 10, 3),
    ],
)
def test_missing_information_metrics_count_each_legitimate_repeat(
    scenario: ReferralScenario,
    duration: float,
    waiting: float,
    touches: int,
    rework: int,
) -> None:
    metrics = _metrics(scenario).metrics

    assert metrics[MetricName.FIRST_PASS_COMPLETE].value is False
    assert metrics[MetricName.CASE_DURATION].value == duration
    assert metrics[MetricName.WAITING_TIME].value == waiting
    assert metrics[MetricName.MANUAL_TOUCHES].value == touches
    assert metrics[MetricName.REWORK_COUNT].value == rework


def test_rerouting_and_failed_scheduling_are_explicit_rework() -> None:
    rerouted = _metrics(referral_recategorised_and_reassigned()).metrics
    failed = _metrics(referral_with_failed_scheduling_attempts()).metrics

    assert rerouted[MetricName.REWORK_COUNT].value == 2
    assert rerouted[MetricName.REASSIGNMENTS].value == 1
    assert rerouted[MetricName.HANDOFFS].value == 4
    assert failed[MetricName.FAILED_SCHEDULING].value == 2
    assert failed[MetricName.REWORK_COUNT].value == 2
    assert failed[MetricName.TIME_TO_BOOKING].value == 59


@pytest.mark.parametrize("scenario", [cancelled_referral(), rejected_referral()])
def test_unbooked_terminal_cases_do_not_receive_false_zero_booking_time(
    scenario: ReferralScenario,
) -> None:
    metrics = _metrics(scenario).metrics

    assert metrics[MetricName.CASE_DURATION].status is MetricStatus.CALCULATED
    assert metrics[MetricName.TIME_TO_BOOKING].value is None
    assert metrics[MetricName.TIME_TO_BOOKING].status is MetricStatus.NOT_APPLICABLE


def test_open_stuck_case_is_partial_and_not_mixed_with_cycle_time() -> None:
    config = AnalysisConfig(analysis_cutoff=datetime(2026, 1, 31, tzinfo=UTC))
    metrics = _metrics(stuck_referral(), config).metrics

    assert metrics[MetricName.CASE_DURATION].status is MetricStatus.PARTIAL
    assert metrics[MetricName.CYCLE_TIME].status is MetricStatus.NOT_APPLICABLE
    assert metrics[MetricName.IS_STUCK].value is True
    assert metrics[MetricName.WAITING_TIME].status is MetricStatus.PARTIAL


def test_event_time_drives_operations_and_ingestion_time_drives_quality() -> None:
    config = AnalysisConfig(delayed_ingestion_threshold_hours=4)
    metrics = _metrics(referral_with_delayed_out_of_order_ingestion(), config).metrics

    assert metrics[MetricName.CASE_DURATION].value == 16
    assert metrics[MetricName.TIME_TO_FIRST_CHECK].value == 2
    assert metrics[MetricName.MAX_INGESTION_DELAY].value == 8
    assert metrics[MetricName.DELAYED_EVENTS].value == 1
    assert metrics[MetricName.OUT_OF_ORDER_INGESTION].value is True


def test_duplicate_source_identity_is_removed_without_mutating_input() -> None:
    scenario = referral_with_duplicate_source_event()
    config = AnalysisConfig()
    result = build_timelines((scenario.case,), scenario.events, config)

    assert len(result.timelines[0].excluded_duplicate_event_ids) == 1
    assert len(result.timelines[0].events) == len(scenario.events) - 1
    assert len(scenario.events) == 10
    assert _metrics(scenario).metrics[MetricName.CASE_DURATION].value == 8
