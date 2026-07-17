"""End-to-end deterministic opportunity identification orchestration."""

import hashlib
from datetime import UTC, datetime

from workflowtwin.opportunities.archetypes import (
    ARCHETYPE_BY_ID,
    ARCHETYPE_LIBRARY_VERSION,
)
from workflowtwin.opportunities.benchmark import evaluate_benchmark
from workflowtwin.opportunities.burden import calculate_observed_burden
from workflowtwin.opportunities.confidence import assess_confidence
from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.deduplication import deduplicate_seeds
from workflowtwin.opportunities.eligibility import assess_eligibility
from workflowtwin.opportunities.evidence import (
    build_evidence_registry,
    validate_input_compatibility,
)
from workflowtwin.opportunities.fingerprint import (
    OPPORTUNITY_ANALYSIS_VERSION,
    opportunity_fingerprint,
)
from workflowtwin.opportunities.graph_data import build_graph_data
from workflowtwin.opportunities.models import (
    EvidenceQualitySummary,
    EvidenceReference,
    EvidenceSourceType,
    OpportunityAnalysis,
    OpportunityAnalysisInput,
    OpportunityCandidate,
    PortfolioSection,
    PortfolioSummary,
    ResearchContradiction,
)
from workflowtwin.opportunities.readiness import assess_readiness
from workflowtwin.opportunities.research import (
    research_pack_fingerprint,
    validate_research_pack,
)
from workflowtwin.opportunities.risk import assess_risk
from workflowtwin.opportunities.rules import (
    RULE_LIBRARY_VERSION,
    OpportunitySeed,
    trigger_opportunity_rules,
)
from workflowtwin.opportunities.scoring import SCORING_MODEL_VERSION, calculate_score
from workflowtwin.opportunities.value import assess_value

FICTIONAL_CONFIRMATION = (
    "Northstar Clinics, all operational data, research participants, quotes, evidence, and "
    "opportunity findings are fictional and cover administrative operations only."
)


def _opportunity_id(seed: OpportunitySeed) -> str:
    identity = "\x1f".join(
        (
            seed.archetype.value,
            seed.cohort_dimension,
            seed.cohort_value,
            seed.workflow_stage,
            RULE_LIBRARY_VERSION,
        )
    )
    return f"opportunity-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"


def _relevant_contradictions(
    qualitative_ids: tuple[str, ...],
    contradictions: tuple[ResearchContradiction, ...],
) -> tuple[ResearchContradiction, ...]:
    selected = set(qualitative_ids)
    return tuple(item for item in contradictions if selected.intersection(item.evidence_ids))


def _future_metrics(seed: OpportunitySeed) -> tuple[str, ...]:
    return ARCHETYPE_BY_ID[seed.archetype].success_measures


class OpportunityIdentifier:
    """Create an auditable portfolio from compatible analytical artifacts."""

    def __init__(self, config: OpportunityConfig) -> None:
        self._config = config

    def analyze(
        self,
        analysis_input: OpportunityAnalysisInput,
        *,
        analysed_at: datetime | None = None,
    ) -> OpportunityAnalysis:
        validate_research_pack(
            analysis_input.research,
            expected_version=self._config.expected_research_pack_version,
        )
        validate_input_compatibility(analysis_input, self._config)
        evidence, contradictions = build_evidence_registry(analysis_input)
        evidence_by_id = {item.evidence_id: item for item in evidence}
        raw_seeds = trigger_opportunity_rules(analysis_input, evidence, self._config)
        seeds = deduplicate_seeds(raw_seeds)
        unranked = tuple(
            self._build_candidate(seed, analysis_input, evidence_by_id, contradictions)
            for seed in seeds
        )
        candidates = self._rank(unranked)
        portfolio = PortfolioSummary(
            candidate_count_before_deduplication=len(raw_seeds),
            candidate_count_after_deduplication=len(candidates),
            controlled_prototype_ids=tuple(
                item.opportunity_id
                for item in candidates
                if item.portfolio_section is PortfolioSection.CONTROLLED_PROTOTYPE
            ),
            further_discovery_ids=tuple(
                item.opportunity_id
                for item in candidates
                if item.portfolio_section is PortfolioSection.FURTHER_DISCOVERY
            ),
            blocked_ids=tuple(
                item.opportunity_id
                for item in candidates
                if item.portfolio_section is PortfolioSection.BLOCKED
            ),
        )
        benchmark = evaluate_benchmark(
            candidates,
            analysis_input.ground_truth,
            analysis_input.baseline.generation_run_id,
        )
        graph_data = build_graph_data(candidates, evidence, contradictions)
        research_fingerprint = research_pack_fingerprint(analysis_input.research)
        fingerprint = opportunity_fingerprint(
            source_dataset_fingerprint=analysis_input.baseline.source_dataset_fingerprint,
            baseline_fingerprint=analysis_input.baseline.analysis_fingerprint,
            process_fingerprint=analysis_input.process.process_analysis_fingerprint,
            research_fingerprint=research_fingerprint,
            archetype_version=ARCHETYPE_LIBRARY_VERSION,
            rule_version=RULE_LIBRARY_VERSION,
            scoring_version=SCORING_MODEL_VERSION,
            config=self._config,
            evidence=evidence,
            contradictions=contradictions,
            candidates=candidates,
            portfolio=portfolio,
            benchmark=benchmark,
        )
        qualitative_count = sum(
            item.source_type is EvidenceSourceType.RESEARCH_OBSERVATION for item in evidence
        )
        warning_count = sum(len(item.warnings) for item in evidence)
        return OpportunityAnalysis(
            analysis_version=OPPORTUNITY_ANALYSIS_VERSION,
            analysis_id=self._config.analysis_id,
            source_dataset_fingerprint=analysis_input.baseline.source_dataset_fingerprint,
            baseline_analysis_fingerprint=analysis_input.baseline.analysis_fingerprint,
            process_analysis_fingerprint=analysis_input.process.process_analysis_fingerprint,
            generation_run_id=analysis_input.baseline.generation_run_id,
            research_pack_version=analysis_input.research.pack_version,
            research_pack_fingerprint=research_fingerprint,
            archetype_library_version=ARCHETYPE_LIBRARY_VERSION,
            rule_library_version=RULE_LIBRARY_VERSION,
            scoring_model_version=SCORING_MODEL_VERSION,
            configuration=self._config.model_dump(mode="json"),
            analysed_at=(analysed_at or datetime.now(UTC)).astimezone(UTC),
            evidence_quality=EvidenceQualitySummary(
                total_evidence_count=len(evidence),
                quantitative_evidence_count=len(evidence) - qualitative_count,
                qualitative_evidence_count=qualitative_count,
                contradiction_count=len(contradictions),
                warning_count=warning_count,
                research_session_count=len(analysis_input.research.sessions),
                research_observation_count=qualitative_count,
            ),
            evidence_references=evidence,
            contradictions=contradictions,
            candidates=candidates,
            portfolio=portfolio,
            benchmark_evaluation=benchmark,
            graph_data=graph_data,
            assumptions=(
                "current burden is associated evidence and not a forecast of removable work",
                "scores order candidates for investigation and do not authorise implementation",
                "confidence measures internal consistency of synthetic evidence only",
            ),
            exclusions=(
                "medical judgement, clinical urgency, diagnosis, treatment, and prognosis",
                "autonomous communication, booking, routing, or ownership changes",
                "individual employee monitoring or protected-attribute comparison",
                "expected benefit, target improvement, ROI, simulation, and automation",
            ),
            warnings=tuple(
                sorted(set(analysis_input.baseline.warnings + analysis_input.process.warnings))
            ),
            opportunity_analysis_fingerprint=fingerprint,
            fictional_data_confirmation=FICTIONAL_CONFIRMATION,
        )

    def _build_candidate(
        self,
        seed: OpportunitySeed,
        analysis_input: OpportunityAnalysisInput,
        evidence_by_id: dict[str, EvidenceReference],
        contradictions: tuple[ResearchContradiction, ...],
    ) -> OpportunityCandidate:
        quantitative = tuple(evidence_by_id[item] for item in seed.quantitative_evidence_ids)
        qualitative = tuple(evidence_by_id[item] for item in seed.qualitative_evidence_ids)
        relevant_contradictions = _relevant_contradictions(
            seed.qualitative_evidence_ids, contradictions
        )
        burden = calculate_observed_burden(analysis_input, seed, self._config)
        source_count = len({item.source_type for item in quantitative})
        value = assess_value(burden, qualitative, source_count)
        readiness = assess_readiness(seed.archetype, bool(qualitative))
        risk = assess_risk(seed.archetype)
        confidence = assess_confidence(quantitative, qualitative, relevant_contradictions)
        eligibility = assess_eligibility(seed, self._config)
        score = calculate_score(value, readiness, confidence, risk, eligibility, self._config)
        section = self._section(eligibility.status.value, score.priority_score)
        archetype = ARCHETYPE_BY_ID[seed.archetype]
        source_fingerprints = tuple(
            sorted({item.source_artifact_fingerprint for item in (*quantitative, *qualitative)})
        )
        return OpportunityCandidate(
            opportunity_id=_opportunity_id(seed),
            opportunity_model_version="1.0.0",
            rule_ids=seed.rule_ids,
            archetype=seed.archetype,
            title=f"{archetype.title}: {seed.cohort_value}",
            cohort_dimension=seed.cohort_dimension,
            cohort_value=seed.cohort_value,
            workflow_stage=seed.workflow_stage,
            problem_statement=seed.problem_statement,
            observed_burden=burden,
            quantitative_evidence_ids=seed.quantitative_evidence_ids,
            qualitative_evidence_ids=seed.qualitative_evidence_ids,
            contradiction_ids=tuple(item.contradiction_id for item in relevant_contradictions),
            eligibility=eligibility,
            value=value,
            readiness=readiness,
            risk=risk,
            confidence=confidence,
            score=score,
            portfolio_section=section,
            portfolio_position=None,
            future_success_metrics=_future_metrics(seed),
            evidence_gaps=confidence.evidence_gaps,
            assumptions=burden.assumptions,
            exclusions=archetype.safety_restrictions,
            warnings=(
                "ranking is decision support and does not authorise a prototype or deployment",
                "no expected benefit or future performance has been calculated",
            ),
            source_artifact_fingerprints=source_fingerprints,
        )

    def _section(self, eligibility: str, priority: float | None) -> PortfolioSection:
        if eligibility in {"out_of_scope", "ineligible", "blocked_by_governance"}:
            return PortfolioSection.BLOCKED
        if (
            eligibility == "eligible_for_controlled_prototype"
            and priority is not None
            and priority >= self._config.prototype_priority_threshold
        ):
            return PortfolioSection.CONTROLLED_PROTOTYPE
        return PortfolioSection.FURTHER_DISCOVERY

    @staticmethod
    def _rank(candidates: tuple[OpportunityCandidate, ...]) -> tuple[OpportunityCandidate, ...]:
        section_order = {
            PortfolioSection.CONTROLLED_PROTOTYPE: 0,
            PortfolioSection.FURTHER_DISCOVERY: 1,
            PortfolioSection.BLOCKED: 2,
        }
        ordered = sorted(
            candidates,
            key=lambda item: (
                section_order[item.portfolio_section],
                -(item.score.priority_score if item.score.priority_score is not None else -1),
                item.opportunity_id,
            ),
        )
        ranked = []
        position = 0
        for item in ordered:
            if item.portfolio_section is not PortfolioSection.BLOCKED:
                position += 1
                ranked.append(item.model_copy(update={"portfolio_position": position}))
            else:
                ranked.append(item)
        return tuple(ranked)
