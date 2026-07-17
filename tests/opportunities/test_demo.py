"""Fixed-demo portfolio, evidence integrity, and scoring tests."""

import pytest

from workflowtwin.opportunities.models import (
    OpportunityAnalysis,
    OpportunityArchetypeId,
    OpportunityCandidate,
    PortfolioSection,
    RequiredControl,
)


def _candidate(
    analysis: OpportunityAnalysis, archetype: OpportunityArchetypeId
) -> OpportunityCandidate:
    return next(item for item in analysis.candidates if item.archetype is archetype)


def test_demo_identifies_and_deduplicates_evidence_backed_portfolio(
    demo_opportunity_analysis: OpportunityAnalysis,
) -> None:
    analysis = demo_opportunity_analysis

    assert analysis.portfolio.candidate_count_before_deduplication == 7
    assert analysis.portfolio.candidate_count_after_deduplication == 6
    assert len(analysis.portfolio.controlled_prototype_ids) == 1
    assert len(analysis.portfolio.further_discovery_ids) == 5
    assert not analysis.portfolio.blocked_ids
    assert analysis.candidates[0].archetype is OpportunityArchetypeId.INTAKE_COMPLETENESS
    assert analysis.candidates[0].cohort_value == "gp_practice"
    assert analysis.benchmark_evaluation.detected_count == 4
    assert set(analysis.benchmark_evaluation.unexpected_opportunity_ids) == {
        _candidate(analysis, OpportunityArchetypeId.STUCK_CASE_MONITORING).opportunity_id,
        _candidate(analysis, OpportunityArchetypeId.DATA_QUALITY_MONITORING).opportunity_id,
    }


def test_core_candidates_have_correct_cohorts_controls_and_metrics(
    demo_opportunity_analysis: OpportunityAnalysis,
) -> None:
    expected = {
        OpportunityArchetypeId.INTAKE_COMPLETENESS: "gp_practice",
        OpportunityArchetypeId.ASSIGNMENT_ROUTING: "neurology",
        OpportunityArchetypeId.SCHEDULING_COORDINATION: "respiratory",
        OpportunityArchetypeId.HANDOFF_REDUCTION: "dermatology",
    }
    for archetype, cohort in expected.items():
        candidate = _candidate(demo_opportunity_analysis, archetype)
        assert candidate.cohort_value == cohort
        assert candidate.quantitative_evidence_ids
        assert candidate.qualitative_evidence_ids
        assert RequiredControl.AUDIT_TRAIL in candidate.risk.required_controls
        assert RequiredControl.PROHIBIT_AUTONOMOUS_EXECUTION in (
            candidate.risk.required_controls
        )
        assert candidate.future_success_metrics
        assert candidate.observed_burden.expected_benefit_gbp is None

    scheduling = _candidate(
        demo_opportunity_analysis, OpportunityArchetypeId.SCHEDULING_COORDINATION
    )
    assert RequiredControl.HUMAN_APPROVAL in scheduling.risk.required_controls
    assert scheduling.portfolio_section is PortfolioSection.FURTHER_DISCOVERY


def test_evidence_and_score_components_reconcile(
    demo_opportunity_analysis: OpportunityAnalysis,
) -> None:
    evidence_ids = [item.evidence_id for item in demo_opportunity_analysis.evidence_references]
    assert len(evidence_ids) == len(set(evidence_ids))
    known = set(evidence_ids)
    node_ids = {item.node_id for item in demo_opportunity_analysis.graph_data.evidence_nodes}
    for candidate in demo_opportunity_analysis.candidates:
        assert set(candidate.quantitative_evidence_ids).issubset(known)
        assert set(candidate.qualitative_evidence_ids).issubset(known)
        assert set(candidate.quantitative_evidence_ids).issubset(node_ids)
        expected = (
            candidate.score.value_contribution
            + candidate.score.readiness_contribution
            + candidate.score.confidence_contribution
            - candidate.score.risk_penalty
        )
        assert candidate.score.priority_score == pytest.approx(expected)


def test_assignment_contradictions_remain_visible_and_reduce_confidence(
    demo_opportunity_analysis: OpportunityAnalysis,
) -> None:
    assignment = _candidate(
        demo_opportunity_analysis, OpportunityArchetypeId.ASSIGNMENT_ROUTING
    )

    assert len(assignment.contradiction_ids) >= 2
    assert assignment.confidence.classification == "low"
    assert "exception handling and operational rules need further discovery" in (
        assignment.readiness.limitations
    )
