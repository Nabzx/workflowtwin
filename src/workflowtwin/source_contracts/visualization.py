"""Frontend-independent chart data for source-contract diagnostics."""

from typing import Any

from workflowtwin.source_contracts.observability import (
    ContractQualityMetrics,
    ObservabilityAnalysis,
)


def source_contract_visualization(
    analysis: ObservabilityAnalysis,
    quality: ContractQualityMetrics,
) -> dict[str, Any]:
    """Return stable series that a future UI can render without domain recomputation."""
    overall = next(
        item
        for item in analysis.ceilings
        if item.cohort_dimension == "overall" and item.cohort_value == "all"
    )
    return {
        "schema_version": 1,
        "missed_positive_categories": [
            {"category": key, "count": value}
            for key, value in sorted(analysis.category_counts.items())
        ],
        "recall_ceiling_funnel": [
            {"stage": "hidden_positives", "count": overall.total_hidden_positives},
            {"stage": "observable", "count": overall.observable_under_contract},
            {
                "stage": "observable_in_time",
                "count": overall.observable_within_useful_window,
            },
            {"stage": "policy_permitted", "count": overall.permitted_under_policy},
            {"stage": "surfaced", "count": overall.surfaced_under_capacity},
        ],
        "quality_rates": [
            {"metric": name, "value": value}
            for name, value in (
                ("supported_form_rate", quality.supported_form_rate),
                ("applicability_coverage", quality.applicability_coverage),
                ("usable_input_coverage", quality.usable_input_coverage),
                ("stale_snapshot_rate", quality.stale_snapshot_rate),
                ("conflict_rate", quality.conflict_rate),
            )
        ],
        "cohort_ceilings": [
            {
                "dimension": item.cohort_dimension,
                "cohort": item.cohort_value,
                "hidden_positives": item.total_hidden_positives,
                "contract_ceiling": item.contract_ceiling,
                "useful_time_ceiling": item.useful_time_ceiling,
            }
            for item in analysis.ceilings
            if item.cohort_dimension != "overall"
        ],
    }
