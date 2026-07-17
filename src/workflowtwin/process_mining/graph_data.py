"""Stable frontend-independent process graph and variant path data."""

from collections import Counter, defaultdict
from uuid import UUID

from workflowtwin.process_mining.activity_mapping import TERMINAL_ACTIVITIES
from workflowtwin.process_mining.models import (
    ActivityStatistics,
    ProcessBottleneckCandidate,
    ProcessGraphData,
    ProcessGraphEdge,
    ProcessGraphNode,
    ProcessLog,
    ProcessVariant,
    TraceConformanceResult,
    TransitionStatistics,
    VariantGraph,
)
from workflowtwin.process_mining.transitions import node_id, transition_id


def build_graph_data(
    process_log: ProcessLog,
    activities: tuple[ActivityStatistics, ...],
    transitions: tuple[TransitionStatistics, ...],
    variants: tuple[ProcessVariant, ...],
    candidates: tuple[ProcessBottleneckCandidate, ...],
    governed_results: tuple[TraceConformanceResult, ...] | None,
) -> ProcessGraphData:
    start_activities = {trace.events[0].activity for trace in process_log.traces}
    activity_deviations: Counter[str] = Counter()
    deviation_cases: dict[str, set[UUID]] = defaultdict(set)
    if governed_results:
        for result in governed_results:
            for deviation in result.deviations:
                if deviation.activity is not None:
                    activity_deviations[deviation.activity] += 1
            if result.deviations:
                for source, target in zip(
                    result.observed_sequence, result.observed_sequence[1:], strict=False
                ):
                    deviation_cases[transition_id(source, target)].add(result.case_id)
    nodes = tuple(
        ProcessGraphNode(
            node_id=node_id(activity.activity),
            activity=activity.activity,
            frequency=activity.frequency,
            distinct_case_count=activity.distinct_case_count,
            is_start=activity.activity in start_activities,
            is_terminal=activity.activity in TERMINAL_ACTIVITIES,
            manual_work_rate=activity.manual_work_rate,
            average_case_position=activity.average_case_position,
            associated_rework_count=activity.repeated_case_count,
            conformance_deviation_count=activity_deviations[activity.activity],
        )
        for activity in activities
    )
    transition_materiality = {
        candidate.subject: candidate.materiality.value
        for candidate in candidates
        if " -> " in candidate.subject
    }
    edges = tuple(
        ProcessGraphEdge(
            edge_id=transition.transition_id,
            source_node_id=node_id(transition.source_activity),
            target_node_id=node_id(transition.target_activity),
            frequency=transition.frequency,
            distinct_case_count=transition.distinct_case_count,
            median_transition_delay_hours=transition.elapsed_hours.median,
            percentiles_hours=transition.elapsed_hours.percentiles,
            median_business_delay_hours=transition.business_hours.median,
            handoff_rate=transition.handoff_rate,
            rework_rate=transition.rework_rate,
            conformance_deviation_rate=len(deviation_cases[transition.transition_id])
            / transition.distinct_case_count,
            bottleneck_materiality=transition_materiality.get(
                f"{transition.source_activity} -> {transition.target_activity}"
            ),
        )
        for transition in transitions
    )
    candidate_subjects = {candidate.subject for candidate in candidates}
    variant_graphs = []
    for variant in variants:
        node_ids = tuple(node_id(activity) for activity in variant.activities)
        edge_ids = tuple(
            transition_id(source, target)
            for source, target in zip(variant.activities, variant.activities[1:], strict=False)
        )
        dominant_outcome = (
            max(variant.outcome_distribution.items(), key=lambda item: (item[1], item[0]))[0]
            if variant.outcome_distribution
            else None
        )
        variant_graphs.append(
            VariantGraph(
                variant_id=variant.variant_id,
                node_ids=node_ids,
                edge_ids=edge_ids,
                case_count=variant.case_count,
                median_duration_hours=variant.duration_hours.median,
                dominant_outcome=dominant_outcome,
                strict_fitness=(
                    variant.conformance.strict_mean_fitness if variant.conformance else None
                ),
                governed_fitness=(
                    variant.conformance.governed_mean_fitness if variant.conformance else None
                ),
                bottleneck_markers=(
                    ("elevated_duration",) if variant.variant_id in candidate_subjects else ()
                ),
            )
        )
    return ProcessGraphData(nodes=nodes, edges=edges, variants=tuple(variant_graphs))
