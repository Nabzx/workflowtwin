"""Deterministic selection of an eligible opportunity from an audited portfolio."""

from workflowtwin.opportunities.models import (
    EligibilityStatus,
    OpportunityAnalysis,
    OpportunityCandidate,
    PortfolioSection,
)


def select_controlled_prototype(
    analysis: OpportunityAnalysis,
) -> OpportunityCandidate:
    candidates = [
        candidate
        for candidate in analysis.candidates
        if candidate.portfolio_section is PortfolioSection.CONTROLLED_PROTOTYPE
        and candidate.eligibility.status is EligibilityStatus.CONTROLLED_PROTOTYPE
        and not candidate.eligibility.hard_failure
    ]
    if not candidates:
        raise ValueError("opportunity portfolio contains no controlled-prototype candidate")
    return sorted(
        candidates,
        key=lambda item: (
            item.risk.score,
            -item.readiness.score,
            -item.confidence.score,
            -(item.score.priority_score if item.score.priority_score is not None else -1),
            item.opportunity_id,
        ),
    )[0]


def validate_selected_opportunity(
    analysis: OpportunityAnalysis, configured_opportunity_id: str
) -> OpportunityCandidate:
    candidate = select_controlled_prototype(analysis)
    if candidate.opportunity_id != configured_opportunity_id:
        raise ValueError(
            "configured opportunity is not the deterministically selected controlled prototype"
        )
    return candidate
