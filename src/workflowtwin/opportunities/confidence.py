"""Internal evidence-consistency confidence, not real-world certainty."""

from workflowtwin.opportunities.models import (
    ConfidenceAssessment,
    EvidenceReference,
    ResearchContradiction,
)


def assess_confidence(
    quantitative: tuple[EvidenceReference, ...],
    qualitative: tuple[EvidenceReference, ...],
    contradictions: tuple[ResearchContradiction, ...],
) -> ConfidenceAssessment:
    source_types = {item.source_type for item in quantitative}
    sample_sizes = [item.sample_size for item in quantitative if item.sample_size is not None]
    warning_count = sum(bool(item.warnings) for item in quantitative)
    score = 35.0
    score += min(30.0, len(source_types) * 10.0)
    score += 15.0 if max(sample_sizes, default=0) >= 100 else 5.0
    score += min(15.0, len(qualitative) * 5.0)
    score -= len(contradictions) * 12.0
    score -= min(15.0, warning_count * 2.0)
    score = max(0.0, min(100.0, score))
    supporting = [
        f"{len(source_types)} independent quantitative source types",
        f"maximum quantitative sample size {max(sample_sizes, default=0)}",
        f"{len(qualitative)} traceable fictional research observations",
    ]
    reducing = ["all operational and research evidence is synthetic"]
    if contradictions:
        reducing.append(f"{len(contradictions)} unresolved research contradiction(s)")
    if warning_count:
        reducing.append(f"{warning_count} quantitative evidence record(s) carry warnings")
    gaps = []
    if not qualitative:
        gaps.append("no role-based qualitative support")
    if len(source_types) < 2:
        gaps.append("fewer than two independent quantitative source types")
    classification = "high" if score >= 75 else "moderate" if score >= 50 else "low"
    return ConfidenceAssessment(
        score=score,
        classification=classification,
        supporting_factors=tuple(supporting),
        reducing_factors=tuple(reducing),
        contradiction_ids=tuple(item.contradiction_id for item in contradictions),
        evidence_gaps=tuple(gaps),
    )
