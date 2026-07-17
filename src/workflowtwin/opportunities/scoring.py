"""Deterministic weighted scoring after hard eligibility gates."""

from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.models import (
    ConfidenceAssessment,
    EligibilityAssessment,
    OpportunityScore,
    ReadinessAssessment,
    RiskAssessment,
    ValueAssessment,
)

SCORING_MODEL_VERSION = "northstar-priority-score-v1"


def calculate_score(
    value: ValueAssessment,
    readiness: ReadinessAssessment,
    confidence: ConfidenceAssessment,
    risk: RiskAssessment,
    eligibility: EligibilityAssessment,
    config: OpportunityConfig,
) -> OpportunityScore:
    value_part = config.value_weight * value.score
    readiness_part = config.readiness_weight * readiness.score
    confidence_part = config.confidence_weight * confidence.score
    risk_part = config.risk_weight * risk.score
    priority = (
        None
        if eligibility.hard_failure
        else value_part + readiness_part + confidence_part - risk_part
    )
    return OpportunityScore(
        value_contribution=value_part,
        readiness_contribution=readiness_part,
        confidence_contribution=confidence_part,
        risk_penalty=risk_part,
        priority_score=priority,
        formula=(
            f"{config.value_weight:g}*value + {config.readiness_weight:g}*readiness + "
            f"{config.confidence_weight:g}*confidence - {config.risk_weight:g}*risk"
        ),
        tie_breaker="opportunity_id ascending",
    )
