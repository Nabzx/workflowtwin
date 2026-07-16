"""Safe JSON, Markdown, and case-level JSONL analysis outputs."""

import json
from pathlib import Path
from typing import Any

from workflowtwin.analytics.models import AnalysisBundle, SummaryMetric


class AnalysisArtifactExistsError(FileExistsError):
    """Raised before any analysis output is allowed to overwrite a file."""


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _number(value: float | None, *, percentage: bool = False) -> str:
    if value is None:
        return "unavailable"
    return f"{value * 100:.1f}%" if percentage else f"{value:.2f}"


def _summary_row(label: str, summary: SummaryMetric) -> str:
    return (
        f"| {label} | {_number(summary.mean)} | {_number(summary.median)} | "
        f"{summary.available_count} | {summary.excluded_count} |"
    )


def render_markdown(bundle: AnalysisBundle) -> str:
    """Render a concise stakeholder report without case event histories."""
    baseline = bundle.baseline
    overall = baseline.overall
    lines = [
        f"# WorkflowTwin baseline: {baseline.analysis_id}",
        "",
        f"> {baseline.fictional_data_confirmation}",
        "",
        "## Scope",
        "",
        f"- Cases analysed: {baseline.case_count:,}",
        f"- Canonical events analysed: {baseline.event_count:,}",
        f"- Dataset fingerprint: `{baseline.source_dataset_fingerprint}`",
        f"- Analysis fingerprint: `{baseline.analysis_fingerprint}`",
        "- Findings are deterministic materiality rules, not AI advice or clinical conclusions.",
        "",
        "## Overall rates",
        "",
        "| Metric | Value | Numerator | Denominator |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, rate in overall.rates.items():
        lines.append(
            f"| {name.replace('_', ' ')} | {_number(rate.value, percentage=True)} | "
            f"{rate.numerator} | {rate.denominator} |"
        )
    lines.extend(
        [
            "",
            "## Duration and effort summaries",
            "",
            "| Metric | Mean | Median | Available | Excluded |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in (
        "case_duration_hours",
        "waiting_time_business_hours",
        "processing_time_estimate_hours",
        "manual_touches",
        "handoffs",
        "rework_count",
        "time_to_first_completeness_check_hours",
        "time_to_appointment_booking_hours",
    ):
        lines.append(_summary_row(name.replace("_", " "), overall.summaries[name]))
    lines.extend(["", "## Baseline findings", ""])
    if baseline.findings:
        for finding in baseline.findings:
            lines.append(
                f"- **{finding.finding_type.replace('_', ' ')}** for "
                f"`{finding.cohort_dimension}={finding.cohort_value}`: "
                f"{finding.observed_value:.3f} versus {finding.baseline_value:.3f} overall "
                f"({finding.materiality.value}; n={finding.cohort_size})."
            )
    else:
        lines.append("No configured material difference met the reporting threshold.")
    quality = baseline.quality
    lines.extend(
        [
            "",
            "## Quality and coverage",
            "",
            f"- Cases excluded entirely: {quality.cases_excluded_entirely}",
            f"- Unsupported schema cases: {quality.unsupported_schema_cases}",
            f"- Ambiguous timelines: {quality.ambiguous_timeline_cases}",
            f"- Identical event timestamps: {quality.identical_timestamp_cases}",
            f"- Cases with delayed ingestion: {quality.delayed_ingestion_cases}",
            f"- Cases with out-of-order ingestion: {quality.out_of_order_ingestion_cases}",
            "",
            "## Synthetic benchmark",
            "",
        ]
    )
    evaluation = baseline.ground_truth_evaluation
    if evaluation.status.value == "evaluated":
        lines.append(
            f"Detected {evaluation.detected_count} of {evaluation.planted_count} planted "
            "operational patterns. This is benchmark verification, not model accuracy."
        )
        for result in evaluation.bottlenecks:
            lines.append(
                f"- {result.bottleneck}: {'detected' if result.detected else 'not detected'} "
                f"({result.expected_cohort})."
            )
    else:
        lines.append("Not evaluated because no separate synthetic ground truth was supplied.")
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            *[f"- {assumption}" for assumption in baseline.assumptions],
            *[f"- {exclusion}" for exclusion in baseline.exclusions],
            "",
        ]
    )
    return "\n".join(lines)


def write_analysis_artifacts(
    bundle: AnalysisBundle,
    *,
    analysis_output: Path,
    report_output: Path,
    case_metrics_output: Path | None = None,
    overwrite: bool = False,
) -> None:
    """Write all requested outputs atomically after a shared overwrite preflight."""
    paths = [analysis_output, report_output]
    if case_metrics_output is not None:
        paths.append(case_metrics_output)
    if not overwrite:
        existing = next((path for path in paths if path.exists()), None)
        if existing is not None:
            raise AnalysisArtifactExistsError(f"analysis artifact already exists: {existing}")
    _write_text(analysis_output, _json(bundle.baseline.model_dump(mode="json")))
    _write_text(report_output, render_markdown(bundle))
    if case_metrics_output is not None:
        content = "".join(
            json.dumps(case.model_dump(mode="json"), sort_keys=True) + "\n"
            for case in bundle.case_metrics
        )
        _write_text(case_metrics_output, content)
