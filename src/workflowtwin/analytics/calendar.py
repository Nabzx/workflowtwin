"""Business-hours calculations for estimated waiting intervals."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from workflowtwin.analytics.config import AnalysisConfig


class AnalysisCalendar:
    def __init__(self, config: AnalysisConfig) -> None:
        self._timezone = ZoneInfo(config.reporting_timezone)
        self._start = config.working_hour_start
        self._end = config.working_hour_end
        self._skip_weekends = config.skip_weekends

    def business_hours_between(self, start: datetime, end: datetime) -> float:
        """Return overlapping configured working hours without mutating boundaries."""
        if end < start:
            raise ValueError("interval end cannot be earlier than start")
        local_start = start.astimezone(self._timezone)
        local_end = end.astimezone(self._timezone)
        current_date = local_start.date()
        total_seconds = 0.0
        while current_date <= local_end.date():
            if not self._skip_weekends or current_date.weekday() < 5:
                day_start = datetime.combine(current_date, time(self._start), self._timezone)
                day_end = datetime.combine(current_date, time(self._end), self._timezone)
                overlap_start = max(local_start, day_start)
                overlap_end = min(local_end, day_end)
                if overlap_end > overlap_start:
                    total_seconds += (overlap_end - overlap_start).total_seconds()
            current_date += timedelta(days=1)
        return total_seconds / 3600
