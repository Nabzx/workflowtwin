"""Transparent operational value assessment from observed burden."""

from workflowtwin.opportunities.models import (
    AssessmentComponent,
    EvidenceReference,
    ObservedBurden,
    ValueAssessment,
)


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, value))


def assess_value(
    burden: ObservedBurden,
    qualitative: tuple[EvidenceReference, ...],
    source_type_count: int,
) -> ValueAssessment:
    volume = _bounded((burden.affected_case_count or 0) / 5)
    manual = _bounded((burden.observed_manual_touches or 0) / 20)
    rework = _bounded((burden.rework_events or 0) / 3)
    delay = _bounded((burden.elapsed_delay_hours or 0) / 2)
    pain_values = {"low": 35.0, "moderate": 65.0, "high": 90.0}
    pain = max((pain_values.get(item.materiality or "", 50.0) for item in qualitative), default=0)
    breadth = _bounded(source_type_count * 20)
    components = (
        AssessmentComponent(
            name="affected_volume", score=volume, rationale="affected cases, capped at 500"
        ),
        AssessmentComponent(
            name="manual_burden", score=manual, rationale="observed touch proxy, capped at 2,000"
        ),
        AssessmentComponent(
            name="rework_burden", score=rework, rationale="associated repeated work, capped at 300"
        ),
        AssessmentComponent(
            name="delay_burden",
            score=delay,
            rationale="associated median elapsed delay, capped at 200 hours",
        ),
        AssessmentComponent(
            name="reported_pain", score=pain, rationale="highest fictional reported severity"
        ),
        AssessmentComponent(
            name="evidence_breadth", score=breadth, rationale="independent evidence-source types"
        ),
    )
    score = sum(item.score for item in components) / len(components)
    classification = "high" if score >= 70 else "moderate" if score >= 45 else "low"
    return ValueAssessment(
        components=components,
        score=score,
        classification=classification,
        raw_measures={
            "affected_case_count": burden.affected_case_count,
            "manual_touches": burden.observed_manual_touches,
            "rework_events": burden.rework_events,
            "elapsed_delay_hours": burden.elapsed_delay_hours,
            "associated_admin_cost_gbp": burden.associated_admin_cost_gbp,
        },
        normalisation=(
            "fixed documented caps on 0-100 components; unobserved burden is unavailable, "
            "not evidence of benefit"
        ),
        assumptions=burden.assumptions,
        warnings=("value represents current associated burden, not expected savings",),
    )
