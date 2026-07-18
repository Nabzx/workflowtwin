"""Frontend-independent chart data for source-contract diagnostics."""

from collections import Counter
from typing import Any

from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2
from workflowtwin.source_contracts.observability import (
    ContractQualityMetrics,
    ObservabilityAnalysis,
)
from workflowtwin.source_contracts.states import ConflictStatus, FreshnessStatus


def source_contract_visualization(
    analysis: ObservabilityAnalysis,
    quality: ContractQualityMetrics,
    snapshots: tuple[IncomingReferralSnapshotV2, ...],
) -> dict[str, Any]:
    """Return stable series that a future UI can render without domain recomputation."""
    overall = next(
        item
        for item in analysis.ceilings
        if item.cohort_dimension == "overall" and item.cohort_value == "all"
    )
    field_states = Counter(
        (field.field_id, field.state.value)
        for snapshot in snapshots
        for field in snapshot.fields
    )
    freshness = Counter(item.freshness.value for item in snapshots)
    conflicts = Counter(item.conflict_status.value for item in snapshots)
    forms = Counter(item.form_version for item in snapshots)
    source_abstentions = Counter(
        item.source_system.value
        for item in snapshots
        if item.freshness is not FreshnessStatus.FRESH
        or item.conflict_status is ConflictStatus.DETECTED
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
        "field_state_distribution": [
            {"field": field, "state": state, "count": count}
            for (field, state), count in sorted(field_states.items())
        ],
        "unknown_versus_absent": [
            {"state": state, "count": count}
            for state, count in (
                (
                    "unknown",
                    sum(
                        value
                        for (_field, name), value in field_states.items()
                        if name == "unknown"
                    ),
                ),
                (
                    "absent",
                    sum(
                        value
                        for (_field, name), value in field_states.items()
                        if name == "absent"
                    ),
                ),
            )
        ],
        "freshness_distribution": [
            {"status": key, "count": value} for key, value in sorted(freshness.items())
        ],
        "conflict_distribution": [
            {"status": key, "count": value} for key, value in sorted(conflicts.items())
        ],
        "form_version_distribution": [
            {"form_version": key, "count": value} for key, value in sorted(forms.items())
        ],
        "source_contract_abstentions": [
            {"source_system": key, "count": value}
            for key, value in sorted(source_abstentions.items())
        ],
        "quality_timeline": [
            {"period": period, **metrics}
            for period, metrics in sorted(quality.by_logical_period.items())
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
