"""Hard gates, missing evidence, confidence, and score behavior."""

from workflowtwin.opportunities.confidence import assess_confidence
from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.eligibility import assess_eligibility
from workflowtwin.opportunities.models import (
    EligibilityStatus,
    OpportunityAnalysis,
    OpportunityArchetypeId,
)
from workflowtwin.opportunities.rules import OpportunitySeed
from workflowtwin.opportunities.scoring import calculate_score


def _seed(evidence: tuple[str, ...] = ("one", "two")) -> OpportunitySeed:
    return OpportunitySeed(
        rule_ids=("test-rule",),
        archetype=OpportunityArchetypeId.INTAKE_COMPLETENESS,
        cohort_dimension="referral_source",
        cohort_value="gp_practice",
        workflow_stage="intake_completeness",
        problem_statement="Administrative test problem.",
        quantitative_evidence_ids=evidence,
        qualitative_evidence_ids=(),
    )


def test_clinical_exclusion_overrides_high_scores(
    demo_opportunity_analysis: OpportunityAnalysis,
) -> None:
    candidate = demo_opportunity_analysis.candidates[0]
    eligibility = assess_eligibility(_seed(), OpportunityConfig(), requires_clinical_judgement=True)
    score = calculate_score(
        candidate.value,
        candidate.readiness,
        candidate.confidence,
        candidate.risk,
        eligibility,
        OpportunityConfig(),
    )

    assert eligibility.status is EligibilityStatus.OUT_OF_SCOPE
    assert eligibility.hard_failure
    assert score.priority_score is None


def test_missing_evidence_does_not_become_confident_or_eligible() -> None:
    eligibility = assess_eligibility(_seed(()), OpportunityConfig())
    confidence = assess_confidence((), (), ())

    assert eligibility.status is EligibilityStatus.NEEDS_EVIDENCE
    assert confidence.classification == "low"
    assert "no role-based qualitative support" in confidence.evidence_gaps


def test_contradiction_reduces_confidence(
    demo_opportunity_analysis: OpportunityAnalysis,
) -> None:
    assignment = next(
        item
        for item in demo_opportunity_analysis.candidates
        if item.archetype is OpportunityArchetypeId.ASSIGNMENT_ROUTING
    )
    by_id = {item.evidence_id: item for item in demo_opportunity_analysis.evidence_references}
    quantitative = tuple(by_id[item] for item in assignment.quantitative_evidence_ids)
    qualitative = tuple(by_id[item] for item in assignment.qualitative_evidence_ids)

    without = assess_confidence(quantitative, qualitative, ())

    assert without.score > assignment.confidence.score
