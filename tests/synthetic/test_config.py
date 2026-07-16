"""Configuration and calendar tests for synthetic generation."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from workflowtwin.synthetic.config import (
    DurationRange,
    GenerationConfig,
    OperationalParameters,
    OutcomeRates,
)
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset
from workflowtwin.synthetic.timing import BusinessCalendar


def test_presets_have_documented_sizes() -> None:
    assert config_for_preset(GenerationPreset.TINY).case_count == 30
    assert config_for_preset(GenerationPreset.DEMO).case_count == 1_000
    assert config_for_preset(GenerationPreset.FULL).case_count == 10_000


def test_invalid_outcome_total_fails_clearly() -> None:
    with pytest.raises(ValidationError, match=r"must sum to 1\.0"):
        OutcomeRates(completed=0.9, cancelled=0.1, rejected=0.1, stuck=0.1)


def test_invalid_duration_calendar_and_mix_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duration maximum"):
        DurationRange(minimum=5, maximum=2)
    with pytest.raises(ValidationError, match="working_hour_end"):
        OperationalParameters(working_hour_start=18, working_hour_end=8)
    with pytest.raises(ValidationError, match="source_system_mix"):
        OperationalParameters(source_system_mix={})


def test_period_and_timezone_must_be_valid() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        GenerationConfig(period_start=datetime(2026, 1, 1))
    with pytest.raises(ValidationError, match="unknown IANA timezone"):
        GenerationConfig(source_timezone="Fictional/Invalid")


def test_calendar_moves_weekend_work_to_monday() -> None:
    config = GenerationConfig(case_count=1)
    calendar = BusinessCalendar(config)
    saturday = datetime(2026, 1, 3, 12, 0, tzinfo=UTC)

    next_work = calendar.next_work_time(saturday)

    assert next_work.weekday() == 0
    assert next_work.hour == config.operations.working_hour_start


def test_calendar_consumes_only_working_hours() -> None:
    config = GenerationConfig(case_count=1)
    calendar = BusinessCalendar(config)
    friday_afternoon = datetime(2026, 1, 2, 16, 0, tzinfo=UTC)

    result = calendar.add_work_hours(friday_afternoon, 4)

    assert result.weekday() == 0
    assert result.hour >= config.operations.working_hour_start
