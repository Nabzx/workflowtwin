"""Safe JSON and recruiter-readable opportunity portfolio artifacts."""

import json
from pathlib import Path
from typing import Any

from workflowtwin.opportunities.models import OpportunityAnalysis, PortfolioSection


class OpportunityArtifactExistsError(FileExistsError):
    """Raised before any opportunity artifact is overwritten."""


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def preflight_paths(paths: tuple[Path, ...], *, overwrite: bool) -> None:
    if overwrite:
        return
    existing = next((path for path in paths if path.exists()), None)
    if existing is not None:
        raise OpportunityArtifactExistsError(f"opportunity artifact already exists: {existing}")


def render_markdown(analysis: OpportunityAnalysis) -> str:
    evidence_by_id = {item.evidence_id: item for item in analysis.evidence_references}
    lines = [
        f"# WorkflowTwin opportunity portfolio: {analysis.analysis_id}",
        "",
        f"> {analysis.fictional_data_confirmation}",
        "",
        "## Executive summary",
        "",
        f"- Evidence references: {analysis.evidence_quality.total_evidence_count:,}.",
        f"- Fictional research: {analysis.evidence_quality.research_session_count} sessions and "
        f"{analysis.evidence_quality.research_observation_count} observations.",
        f"- Candidates after deduplication: "
        f"{analysis.portfolio.candidate_count_after_deduplication}.",
        f"- Controlled prototype candidates: {len(analysis.portfolio.controlled_prototype_ids)}.",
        f"- Further-discovery candidates: {len(analysis.portfolio.further_discovery_ids)}.",
        f"- Blocked candidates: {len(analysis.portfolio.blocked_ids)}.",
        "- Ranking supports investigation only; it does not authorise design, deployment, "
        "or action.",
        "- Observed burden and addressable upper bounds are not expected benefits or ROI.",
        "",
        "## Evidence sources",
        "",
        f"- Dataset: `{analysis.source_dataset_fingerprint}`",
        f"- Baseline: `{analysis.baseline_analysis_fingerprint}`",
        f"- Process analysis: `{analysis.process_analysis_fingerprint}`",
        f"- Research pack: `{analysis.research_pack_fingerprint}`",
        "",
        "## Portfolio comparison",
        "",
        "| Position | Opportunity | Section | Value | Readiness | Confidence | Risk | "
        "Priority | Cases |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in analysis.candidates:
        priority = (
            "blocked" if item.score.priority_score is None else f"{item.score.priority_score:.2f}"
        )
        lines.append(
            f"| {item.portfolio_position or '-'} | `{item.opportunity_id}` | "
            f"{item.portfolio_section.value} | {item.value.score:.1f} | "
            f"{item.readiness.score:.1f} | {item.confidence.score:.1f} | "
            f"{item.risk.score:.1f} | {priority} | "
            f"{item.observed_burden.affected_case_count or 'unavailable'} |"
        )
    for heading, section in (
        ("Eligible for controlled prototype", PortfolioSection.CONTROLLED_PROTOTYPE),
        ("Needs further discovery", PortfolioSection.FURTHER_DISCOVERY),
        ("Blocked or out of scope", PortfolioSection.BLOCKED),
    ):
        lines.extend(["", f"## {heading}", ""])
        members = [item for item in analysis.candidates if item.portfolio_section is section]
        if not members:
            lines.append("No candidates in this section.")
            continue
        for item in members:
            quantitative = [
                evidence_by_id[evidence_id].metric_or_observation
                for evidence_id in item.quantitative_evidence_ids[:3]
            ]
            qualitative = [
                evidence_by_id[evidence_id].source_record_id
                for evidence_id in item.qualitative_evidence_ids[:3]
            ]
            lines.extend(
                [
                    f"### {item.title}",
                    "",
                    item.problem_statement,
                    "",
                    f"- Cohort: `{item.cohort_dimension}={item.cohort_value}`.",
                    f"- Observed cases: {item.observed_burden.affected_case_count}; "
                    f"manual-touch hours proxy: "
                    f"{item.observed_burden.estimated_manual_touch_hours}.",
                    f"- Eligibility: {item.eligibility.status.value}; "
                    f"risk: {item.risk.level.value}.",
                    f"- Required controls: "
                    f"{', '.join(control.value for control in item.risk.required_controls)}.",
                    f"- Future evaluation metrics: {', '.join(item.future_success_metrics)}.",
                    "- Evidence chain: "
                    f"baseline/process ({'; '.join(quantitative)}) -> "
                    f"research ({', '.join(qualitative) or 'gap'}) -> "
                    f"eligibility ({item.eligibility.status.value}) -> "
                    f"controls -> {item.portfolio_section.value}.",
                ]
            )
    lines.extend(["", "## Evidence contradictions", ""])
    if analysis.contradictions:
        for contradiction in analysis.contradictions:
            lines.append(
                f"- `{contradiction.contradiction_id}`: {contradiction.nature} "
                f"Future discovery: {contradiction.future_discovery_need}"
            )
    else:
        lines.append("No structured contradictions were supplied.")
    benchmark = analysis.benchmark_evaluation
    lines.extend(
        [
            "",
            "## Synthetic benchmark evaluation",
            "",
            f"Status: {benchmark.status}; detected {benchmark.detected_count} of "
            f"{benchmark.expected_count} expected opportunities.",
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in analysis.assumptions],
            *[f"- Excluded: {item}" for item in analysis.exclusions],
            "- No LLM recommendation, simulation, expected improvement, or automation is present.",
            "",
            f"Opportunity fingerprint: `{analysis.opportunity_analysis_fingerprint}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_opportunity_artifacts(
    analysis: OpportunityAnalysis,
    *,
    analysis_output: Path,
    report_output: Path,
    portfolio_output: Path,
    evidence_output: Path,
    overwrite: bool,
) -> None:
    preflight_paths(
        (analysis_output, report_output, portfolio_output, evidence_output),
        overwrite=overwrite,
    )
    _write(analysis_output, _json(analysis.model_dump(mode="json")))
    _write(report_output, render_markdown(analysis))
    _write(
        portfolio_output,
        _json([item.model_dump(mode="json") for item in analysis.graph_data.portfolio_points]),
    )
    _write(
        evidence_output,
        _json(
            {
                "nodes": [
                    item.model_dump(mode="json") for item in analysis.graph_data.evidence_nodes
                ],
                "links": [
                    item.model_dump(mode="json") for item in analysis.graph_data.evidence_links
                ],
            }
        ),
    )
