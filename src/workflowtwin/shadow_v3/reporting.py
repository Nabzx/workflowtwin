"""Human-readable strict-v3 development, validation, and holdout reports."""

from collections import Counter

from workflowtwin.shadow_v3.models import V3Evaluation


def render_v3_report(
    evaluations: tuple[V3Evaluation, ...],
    *,
    title: str,
    holdout_status: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        "> Northstar Clinics, source systems, review capacity, and results are fictional.",
        "> Administrative recommendation-only shadow evaluation; no workflow action occurs.",
        "",
        "| Dataset | Cases | Positives | Precision | Recall | Ceiling | Relative | Surfaced | "
        "Assessment |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for evaluation in evaluations:
        detector = evaluation.detector
        lines.append(
            f"| {evaluation.manifest.dataset_id} | {detector.incoming_cases} | "
            f"{detector.detector_positives} | {(detector.precision or 0):.2%} | "
            f"{(detector.recall or 0):.2%} | "
            f"{(detector.observable_recall_ceiling or 0):.2%} | "
            f"{(detector.ceiling_relative_recall or 0):.2%} | "
            f"{detector.surfaced_recommendations} | {evaluation.promotion_assessment} |"
        )
    residual = Counter(
        item.primary_category.value
        for evaluation in evaluations
        for item in evaluation.missed_positives
    )
    lines.extend(["", "## Residual missed positives", ""])
    lines.extend(f"- `{name}`: {count}" for name, count in sorted(residual.items()))
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"Holdout V3 status: **{holdout_status}**.",
            "",
            "A passed detector gate would authorise only the next design decision. It would not "
            "authorise production, autonomous action, patient contact, diagnosis, treatment, or "
            "real-world impact claims.",
        ]
    )
    return "\n".join(lines) + "\n"
