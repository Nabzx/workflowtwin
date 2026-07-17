"""Small deterministic statistical helpers shared by process modules."""

from statistics import fmean, median

from workflowtwin.process_mining.models import NumericSummary


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def numeric_summary(values: list[float], percentiles: tuple[float, ...]) -> NumericSummary:
    return NumericSummary(
        count=len(values),
        mean=fmean(values) if values else None,
        median=median(values) if values else None,
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
        percentiles={
            f"p{quantile * 100:g}": percentile(values, quantile) for quantile in percentiles
        }
        if values
        else {},
    )
