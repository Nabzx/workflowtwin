"""Post-generation benchmark checks against separate synthetic ground truth."""

from dataclasses import dataclass

from workflowtwin.opportunities.models import (
    OpportunityArchetypeId,
    OpportunityBenchmarkEvaluation,
    OpportunityBenchmarkResult,
    OpportunityCandidate,
    PortfolioSection,
)
from workflowtwin.synthetic.models import GenerationGroundTruth


@dataclass(frozen=True, slots=True)
class ExpectedOpportunity:
    name: str
    archetype: OpportunityArchetypeId
    dimension: str
    value: str


EXPECTED = (
    ExpectedOpportunity(
        "gp_practice_completeness",
        OpportunityArchetypeId.INTAKE_COMPLETENESS,
        "referral_source",
        "gp_practice",
    ),
    ExpectedOpportunity(
        "neurology_assignment",
        OpportunityArchetypeId.ASSIGNMENT_ROUTING,
        "service_line",
        "neurology",
    ),
    ExpectedOpportunity(
        "respiratory_scheduling",
        OpportunityArchetypeId.SCHEDULING_COORDINATION,
        "service_line",
        "respiratory",
    ),
    ExpectedOpportunity(
        "dermatology_handoff",
        OpportunityArchetypeId.HANDOFF_REDUCTION,
        "service_line",
        "dermatology",
    ),
)


def evaluate_benchmark(
    candidates: tuple[OpportunityCandidate, ...],
    ground_truth: GenerationGroundTruth | None,
    generation_run_id: str | None,
) -> OpportunityBenchmarkEvaluation:
    if ground_truth is None:
        return OpportunityBenchmarkEvaluation(
            status="not_evaluated",
            results=(),
            detected_count=0,
            expected_count=0,
            false_negatives=(),
            unexpected_opportunity_ids=(),
            notes=("no separate synthetic ground truth was supplied",),
        )
    if generation_run_id is None or ground_truth.run_id != generation_run_id:
        raise ValueError("ground truth generation run does not match opportunity inputs")
    results = []
    matched = set()
    for expected in EXPECTED:
        candidate = next(
            (
                item
                for item in candidates
                if item.archetype is expected.archetype
                and item.cohort_dimension == expected.dimension
                and item.cohort_value == expected.value
            ),
            None,
        )
        if candidate is not None:
            matched.add(candidate.opportunity_id)
        results.append(
            OpportunityBenchmarkResult(
                expected_opportunity=expected.name,
                detected=candidate is not None,
                opportunity_id=candidate.opportunity_id if candidate else None,
                expected_archetype=expected.archetype,
                expected_cohort=f"{expected.dimension}={expected.value}",
                evidence_references_valid=bool(candidate and candidate.quantitative_evidence_ids),
                research_linked=bool(candidate and candidate.qualitative_evidence_ids),
                controls_appropriate=bool(
                    candidate
                    and candidate.risk.required_controls
                    and candidate.risk.level.value != "prohibited"
                ),
                portfolio_section_appropriate=bool(
                    candidate
                    and candidate.portfolio_section
                    in {
                        PortfolioSection.CONTROLLED_PROTOTYPE,
                        PortfolioSection.FURTHER_DISCOVERY,
                    }
                ),
            )
        )
    return OpportunityBenchmarkEvaluation(
        status="evaluated",
        results=tuple(results),
        detected_count=sum(item.detected for item in results),
        expected_count=len(results),
        false_negatives=tuple(item.expected_opportunity for item in results if not item.detected),
        unexpected_opportunity_ids=tuple(
            item.opportunity_id for item in candidates if item.opportunity_id not in matched
        ),
        notes=(
            "benchmark labels were consulted only after candidate scoring and portfolio placement",
            "this is deterministic synthetic coverage evaluation, not predictive accuracy",
        ),
    )
