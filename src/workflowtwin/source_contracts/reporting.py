"""Recruiter-readable source-contract analysis reporting."""

from workflowtwin.source_contracts.observability import (
    ContractQualityMetrics,
    ObservabilityAnalysis,
)


def render_source_contract_report(
    analysis: ObservabilityAnalysis,
    quality: ContractQualityMetrics,
) -> str:
    overall = next(
        item
        for item in analysis.ceilings
        if item.cohort_dimension == "overall" and item.cohort_value == "all"
    )
    lines = [
        "# Missed-positive source-contract analysis",
        "",
        "> Northstar Clinics, its source systems, records, and results are fictional.",
        "> Administrative recommendation-only analysis; no workflow action or clinical logic.",
        "",
        "## Evidence chain",
        "",
        "Strict-v2 recall failure -> missed-positive taxonomy -> source observability analysis -> "
        "explicit V2 source contract -> conditional strict-v3 pre-registration.",
        "",
        "## Observability",
        "",
        f"- Hidden positives: {overall.total_hidden_positives}",
        f"- Observable under V2: {overall.observable_under_contract}",
        f"- Observable within useful time: {overall.observable_within_useful_window}",
        f"- Contract recall ceiling: {(overall.contract_ceiling or 0):.2%}",
        f"- Useful-time recall ceiling: {(overall.useful_time_ceiling or 0):.2%}",
        "",
        "## Missed-positive taxonomy",
        "",
    ]
    lines.extend(f"- `{category}`: {count}" for category, count in analysis.category_counts.items())
    lines.extend(
        [
            "",
            "## Contract quality",
            "",
            f"- Supported-form rate: {quality.supported_form_rate:.2%}",
            f"- Applicability coverage: {quality.applicability_coverage:.2%}",
            f"- Requirements-version agreement: {quality.requirements_version_agreement:.2%}",
            f"- Freshness exceptions: {quality.stale_snapshot_rate:.2%}",
            f"- Source conflicts: {quality.conflict_rate:.2%}",
            f"- Usable-input coverage: {quality.usable_input_coverage:.2%}",
            "",
            "Unknown is never treated as absent. Stale, conflicting, mismatched, and unsupported "
            "states require abstention. Truth labels are used only after source publication is "
            "frozen.",
        ]
    )
    return "\n".join(lines) + "\n"
