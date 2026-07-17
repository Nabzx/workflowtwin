"""Safe JSON, Markdown, graph, and optional case-level process artifacts."""

import json
from pathlib import Path
from typing import Any

from workflowtwin.process_mining.models import ProcessMiningBundle


class ProcessArtifactExistsError(FileExistsError):
    """Raised before process outputs overwrite existing artifacts."""


def preflight_paths(paths: tuple[Path | None, ...], *, overwrite: bool) -> None:
    if overwrite:
        return
    existing = next((path for path in paths if path is not None and path.exists()), None)
    if existing is not None:
        raise ProcessArtifactExistsError(f"process artifact already exists: {existing}")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _percent(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.1%}"


def render_markdown(bundle: ProcessMiningBundle) -> str:
    analysis = bundle.analysis
    complexity = analysis.complexity
    lines = [
        f"# WorkflowTwin process analysis: {analysis.analysis_id}",
        "",
        f"> {analysis.fictional_data_confirmation}",
        "",
        "## Executive operational summary",
        "",
        f"- {analysis.case_count:,} traces and {analysis.event_count:,} canonical events.",
        f"- {complexity.distinct_activity_count} activities, "
        f"{complexity.distinct_transition_count} transitions, and "
        f"{complexity.distinct_variant_count} variants.",
        f"- Top variant coverage: {_percent(complexity.top_1_variant_coverage)}; "
        f"top five: {_percent(complexity.top_5_variant_coverage)}; "
        f"top ten: {_percent(complexity.top_10_variant_coverage)}.",
        "- Conformance describes structural fit, not speed, quality, or clinical outcomes.",
        "",
        "## Top variants",
        "",
        "| Variant | Cases | Share | Median hours | Markers |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for variant in analysis.variants[:20]:
        duration = (
            "unavailable"
            if variant.duration_hours.median is None
            else f"{variant.duration_hours.median:.2f}"
        )
        lines.append(
            f"| `{variant.variant_id}` | {variant.case_count} | "
            f"{variant.case_percentage:.1%} | {duration} | {', '.join(variant.markers) or 'none'} |"
        )
    lines.extend(["", "## Slowest material transitions", ""])
    slow = sorted(
        analysis.transition_statistics,
        key=lambda item: item.elapsed_hours.median or -1,
        reverse=True,
    )[:10]
    for transition in slow:
        lines.append(
            f"- {transition.source_activity} -> {transition.target_activity}: "
            f"median {transition.elapsed_hours.median or 0:.2f} elapsed hours "
            f"across {transition.frequency} occurrences."
        )
    lines.extend(["", "## Most frequent loops", ""])
    for loop in sorted(analysis.loops, key=lambda item: -item.occurrence_count)[:10]:
        lines.append(
            f"- {' -> '.join(loop.activities)}: {loop.occurrence_count} occurrences in "
            f"{loop.distinct_case_count} cases."
        )
    lines.extend(["", "## Strict versus governed conformance", ""])
    for label, summary in (
        ("Strict", analysis.strict_conformance),
        ("Governed", analysis.governed_conformance),
    ):
        if summary:
            lines.append(
                f"- {label}: {_percent(summary.fully_conforming_rate)} fully conforming; "
                f"median fitness {summary.median_fitness or 0:.3f}; "
                f"{summary.unavailable_count} unavailable."
            )
    lines.extend(["", "## Most common deviations", ""])
    if analysis.deviation_summary:
        for category, count in sorted(
            analysis.deviation_summary.items(), key=lambda item: (-item[1], item[0])
        )[:10]:
            lines.append(f"- {category.replace('_', ' ')}: {count} cases or occurrences.")
    else:
        lines.append("No governed-reference deviations were observed.")
    lines.extend(["", "## Candidate bottlenecks", ""])
    for candidate in analysis.bottleneck_candidates[:20]:
        cohort = (
            f" ({candidate.cohort_dimension}={candidate.cohort_value})"
            if candidate.cohort_dimension
            else ""
        )
        lines.append(
            f"- **{candidate.candidate_type.replace('_', ' ')}**: {candidate.subject}{cohort}; "
            f"{candidate.case_count} cases; {candidate.materiality.value}."
        )
    lines.extend(["", "## Baseline reconciliation", ""])
    if analysis.baseline_reconciliation:
        for result in analysis.baseline_reconciliation:
            lines.append(
                f"- `{result.baseline_finding_id}`: "
                f"{'supported' if result.supports_finding else 'not independently supported'} "
                f"by {len(result.supporting_process_ids)} process candidate(s)."
            )
    else:
        lines.append("No baseline analysis was supplied for reconciliation.")
    if analysis.visualisation_artifacts:
        lines.extend(
            [
                "",
                "## Static process artefacts",
                "",
            ]
        )
        lines.extend(f"- `{path}`" for path in analysis.visualisation_artifacts)
    evaluation = analysis.ground_truth_evaluation
    lines.extend(
        [
            "",
            "## Synthetic benchmark evaluation",
            "",
            f"Status: {evaluation.status}. Detected {evaluation.detected_count} of "
            f"{evaluation.planted_count} planted patterns.",
            "",
            "## Data-quality and interpretation limits",
            "",
            *[f"- {warning}" for warning in analysis.log_quality.warnings],
            *[f"- {assumption}" for assumption in analysis.assumptions],
            "",
            f"Process fingerprint: `{analysis.process_analysis_fingerprint}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_process_artifacts(
    bundle: ProcessMiningBundle,
    *,
    analysis_output: Path,
    report_output: Path,
    graph_output: Path,
    case_output: Path | None,
    overwrite: bool,
) -> None:
    preflight_paths(
        (analysis_output, report_output, graph_output, case_output), overwrite=overwrite
    )
    _write_text(analysis_output, _json(bundle.analysis.model_dump(mode="json")))
    _write_text(report_output, render_markdown(bundle))
    _write_text(graph_output, _json(bundle.analysis.graph_data.model_dump(mode="json")))
    if case_output is not None:
        case_output.parent.mkdir(parents=True, exist_ok=True)
        temporary = case_output.with_suffix(f"{case_output.suffix}.tmp")
        with temporary.open("w", encoding="utf-8") as output:
            for result in bundle.case_results:
                output.write(json.dumps(result.model_dump(mode="json"), sort_keys=True) + "\n")
        temporary.replace(case_output)
