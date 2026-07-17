"""Frontend-independent portfolio points and evidence-network data."""

import hashlib

from workflowtwin.opportunities.models import (
    EvidenceNetworkLink,
    EvidenceNetworkNode,
    EvidenceReference,
    OpportunityCandidate,
    OpportunityGraphData,
    PortfolioPoint,
    ResearchContradiction,
)


def _link_id(source: str, target: str, relationship: str) -> str:
    identity = f"{source}\x1f{target}\x1f{relationship}"
    return f"link-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"


def build_graph_data(
    candidates: tuple[OpportunityCandidate, ...],
    evidence: tuple[EvidenceReference, ...],
    contradictions: tuple[ResearchContradiction, ...],
) -> OpportunityGraphData:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    referenced_ids = {
        evidence_id
        for candidate in candidates
        for evidence_id in (
            *candidate.quantitative_evidence_ids,
            *candidate.qualitative_evidence_ids,
        )
    }
    nodes = [
        EvidenceNetworkNode(
            node_id=candidate.opportunity_id,
            node_type="opportunity",
            label=candidate.title,
            source_pointer=None,
        )
        for candidate in candidates
    ]
    nodes.extend(
        EvidenceNetworkNode(
            node_id=item.evidence_id,
            node_type=item.source_type.value,
            label=item.metric_or_observation,
            source_pointer=item.source_pointer,
        )
        for item in evidence
        if item.evidence_id in referenced_ids
    )
    links = []
    for candidate in candidates:
        for evidence_id in candidate.quantitative_evidence_ids:
            links.append(
                EvidenceNetworkLink(
                    link_id=_link_id(evidence_id, candidate.opportunity_id, "supports"),
                    source_node_id=evidence_id,
                    target_node_id=candidate.opportunity_id,
                    relationship="supports",
                )
            )
        for evidence_id in candidate.qualitative_evidence_ids:
            links.append(
                EvidenceNetworkLink(
                    link_id=_link_id(evidence_id, candidate.opportunity_id, "qualifies"),
                    source_node_id=evidence_id,
                    target_node_id=candidate.opportunity_id,
                    relationship="qualifies",
                )
            )
    for contradiction in contradictions:
        if all(
            item in evidence_by_id and item in referenced_ids for item in contradiction.evidence_ids
        ):
            source, target = contradiction.evidence_ids
            links.append(
                EvidenceNetworkLink(
                    link_id=_link_id(source, target, "contradicts"),
                    source_node_id=source,
                    target_node_id=target,
                    relationship="contradicts",
                )
            )
    points = tuple(
        PortfolioPoint(
            opportunity_id=item.opportunity_id,
            value_score=item.value.score,
            readiness_score=item.readiness.score,
            confidence_score=item.confidence.score,
            risk_score=item.risk.score,
            priority_score=item.score.priority_score,
            eligibility=item.eligibility.status,
            portfolio_section=item.portfolio_section,
            affected_case_count=item.observed_burden.affected_case_count,
            archetype=item.archetype,
            cohort_dimension=item.cohort_dimension,
            cohort_value=item.cohort_value,
            evidence_count=len(item.quantitative_evidence_ids) + len(item.qualitative_evidence_ids),
        )
        for item in candidates
    )
    return OpportunityGraphData(
        portfolio_points=points,
        evidence_nodes=tuple(sorted(nodes, key=lambda item: item.node_id)),
        evidence_links=tuple(sorted(links, key=lambda item: item.link_id)),
    )
