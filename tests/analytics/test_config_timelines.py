"""Configuration validation and imperfect-timeline behavior."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.calendar import AnalysisCalendar
from workflowtwin.analytics.case_metrics import calculate_case_metrics
from workflowtwin.analytics.config import AnalysisConfig, DuplicatePolicy
from workflowtwin.analytics.fingerprint import dataset_fingerprint
from workflowtwin.analytics.models import AnalysisInput, MetricName, MetricStatus
from workflowtwin.analytics.timelines import build_timelines
from workflowtwin.domain.referrals.fixtures import (
    referral_with_duplicate_source_event,
    straight_through_successful_referral,
    stuck_referral,
)


@pytest.mark.parametrize(
    "overrides",
    [
        {"analysis_cutoff": datetime(2026, 1, 1)},
        {"reporting_timezone": "Mars/Olympus"},
        {
            "period_start": datetime(2026, 2, 1, tzinfo=UTC),
            "period_end": datetime(2026, 1, 1, tzinfo=UTC),
        },
        {
            "period_end": datetime(2028, 1, 1, tzinfo=UTC),
            "analysis_cutoff": datetime(2027, 1, 1, tzinfo=UTC),
        },
        {"working_hour_start": 18, "working_hour_end": 18},
        {"percentiles": (0.9, 0.5)},
        {"percentiles": (0.0,)},
    ],
)
def test_invalid_analysis_configuration_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AnalysisConfig(**overrides)  # type: ignore[arg-type]


def test_business_calendar_skips_weekend_and_out_of_hours() -> None:
    calendar = AnalysisCalendar(AnalysisConfig())

    hours = calendar.business_hours_between(
        datetime(2026, 1, 9, 16, tzinfo=UTC),
        datetime(2026, 1, 12, 10, tzinfo=UTC),
    )

    assert hours == 4
    with pytest.raises(ValueError, match="interval end"):
        calendar.business_hours_between(
            datetime(2026, 1, 12, 10, tzinfo=UTC),
            datetime(2026, 1, 12, 9, tzinfo=UTC),
        )


def test_period_filter_orphan_and_identical_timestamps_are_reported() -> None:
    scenario = referral_with_duplicate_source_event()
    orphan = scenario.events[0].model_copy(update={"referral_case_id": uuid4()})
    same_time = scenario.events[-1].model_copy(
        update={
            "id": uuid4(),
            "external_event_id": "SYNTH:DUPLICATE0001:SAME-TIME",
            "event_at": scenario.events[-2].event_at,
        }
    )
    included = build_timelines(
        (scenario.case,),
        (*scenario.events, same_time, orphan),
        AnalysisConfig(),
    )
    excluded = build_timelines(
        (scenario.case,),
        scenario.events,
        AnalysisConfig(period_start=datetime(2026, 2, 1, tzinfo=UTC)),
    )

    assert included.orphan_event_count == 1
    assert included.timelines[0].identical_event_timestamps is True
    assert len(included.timelines[0].excluded_duplicate_event_ids) == 1
    assert excluded.period_excluded_case_count == 1
    assert not excluded.timelines


def test_missing_boundaries_are_unavailable_and_open_cases_can_be_excluded() -> None:
    scenario = straight_through_successful_referral()
    events = tuple(
        event for event in scenario.events if event.event_type.value != "referral_received"
    )
    config = AnalysisConfig()
    timeline = build_timelines((scenario.case,), events, config).timelines[0]
    metrics = calculate_case_metrics(timeline, config).metrics

    assert metrics[MetricName.CASE_DURATION].status is MetricStatus.UNAVAILABLE
    assert metrics[MetricName.TIME_TO_FIRST_CHECK].value is None

    open_scenario = stuck_referral()
    excluded_config = AnalysisConfig(include_open_cases=False)
    open_metrics = calculate_case_metrics(
        build_timelines((open_scenario.case,), open_scenario.events, excluded_config).timelines[0],
        excluded_config,
    ).metrics
    assert open_metrics[MetricName.CASE_DURATION].status is MetricStatus.EXCLUDED


def test_reject_duplicate_policy_excludes_only_affected_timeline() -> None:
    duplicate = referral_with_duplicate_source_event()
    straight = straight_through_successful_referral()
    cases = (duplicate.case, straight.case)
    events = (*duplicate.events, *straight.events)
    fingerprint = dataset_fingerprint(cases, events)

    baseline = (
        BaselineAnalyzer(AnalysisConfig(duplicate_policy=DuplicatePolicy.REJECT))
        .analyze(AnalysisInput(cases, events, fingerprint))
        .baseline
    )

    assert baseline.case_count == 1
    assert baseline.quality.cases_excluded_entirely == 1


def test_configured_and_supplied_fingerprint_mismatches_are_rejected() -> None:
    scenario = straight_through_successful_referral()
    actual = dataset_fingerprint((scenario.case,), scenario.events)

    with pytest.raises(ValueError, match="input dataset fingerprint"):
        BaselineAnalyzer(AnalysisConfig()).analyze(
            AnalysisInput((scenario.case,), scenario.events, "0" * 64)
        )
    with pytest.raises(ValueError, match="configured source dataset fingerprint"):
        BaselineAnalyzer(AnalysisConfig(source_dataset_fingerprint="1" * 64)).analyze(
            AnalysisInput((scenario.case,), scenario.events, actual)
        )
