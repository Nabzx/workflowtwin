"""Deterministic working-calendar timing helpers."""

from datetime import datetime, time, timedelta
from random import Random
from zoneinfo import ZoneInfo

from workflowtwin.synthetic.config import DurationRange, GenerationConfig

WEEKDAY_VOLUME_WEIGHTS = (1.20, 1.15, 1.05, 1.00, 0.85, 0.25, 0.15)


class BusinessCalendar:
    """Apply Northstar working hours without becoming a simulation framework."""

    def __init__(self, config: GenerationConfig) -> None:
        self._timezone = ZoneInfo(config.source_timezone)
        self._start_hour = config.operations.working_hour_start
        self._end_hour = config.operations.working_hour_end
        self._skip_weekends = config.operations.skip_weekends

    def random_arrival(self, rng: Random, config: GenerationConfig) -> datetime:
        """Choose a volume-weighted local arrival and return its UTC instant."""
        day_offsets = list(range(config.operating_days))
        weights = []
        local_start = config.period_start.astimezone(self._timezone)
        for offset in day_offsets:
            day = local_start + timedelta(days=offset)
            weekly_factor = 1.08 if (offset // 7) % 2 == 0 else 0.92
            weights.append(WEEKDAY_VOLUME_WEIGHTS[day.weekday()] * weekly_factor)
        day_offset = rng.choices(day_offsets, weights=weights, k=1)[0]
        day = local_start + timedelta(days=day_offset)
        hour = rng.uniform(7.0, 20.5)
        local_arrival = datetime.combine(day.date(), time(), tzinfo=self._timezone) + timedelta(
            hours=hour
        )
        return local_arrival.astimezone(config.period_start.tzinfo)

    def sample_duration(self, rng: Random, duration: DurationRange) -> float:
        return rng.uniform(duration.minimum, duration.maximum)

    def next_work_time(self, value: datetime) -> datetime:
        """Move an instant to the next local working period when necessary."""
        local = value.astimezone(self._timezone)
        while self._skip_weekends and local.weekday() >= 5:
            local = datetime.combine(
                local.date() + timedelta(days=1),
                time(self._start_hour),
                tzinfo=self._timezone,
            )
        if local.hour < self._start_hour:
            local = datetime.combine(local.date(), time(self._start_hour), tzinfo=self._timezone)
        elif local.hour >= self._end_hour:
            local = datetime.combine(
                local.date() + timedelta(days=1),
                time(self._start_hour),
                tzinfo=self._timezone,
            )
            return self.next_work_time(local)
        return local.astimezone(value.tzinfo)

    def add_work_hours(self, value: datetime, hours: float) -> datetime:
        """Consume duration only during configured working hours."""
        current = self.next_work_time(value).astimezone(self._timezone)
        remaining = hours
        while remaining > 0:
            end_of_day = datetime.combine(
                current.date(), time(self._end_hour), tzinfo=self._timezone
            )
            available = (end_of_day - current).total_seconds() / 3600
            if remaining <= available:
                return (current + timedelta(hours=remaining)).astimezone(value.tzinfo)
            remaining -= available
            current = self.next_work_time(end_of_day + timedelta(seconds=1)).astimezone(
                self._timezone
            )
        return current.astimezone(value.tzinfo)
