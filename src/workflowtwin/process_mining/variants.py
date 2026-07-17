"""Stable process variants and transparent complexity measures."""

import hashlib
import json
import math
from collections import Counter, defaultdict
from statistics import fmean, median
from uuid import UUID

from workflowtwin.analytics.models import CaseMetrics, MetricName
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import (
    ProcessComplexity,
    ProcessLog,
    ProcessVariant,
    VariantClassification,
    VariantConformanceSummary,
)
from workflowtwin.process_mining.statistics import numeric_summary


def variant_id(activities: tuple[str, ...], mapping_version: str) -> str:
    canonical = json.dumps(
        {"activity_mapping_version": mapping_version, "activities": activities},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"variant-{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"


def variant_markers(activities: tuple[str, ...]) -> tuple[str, ...]:
    markers = []
    mapping = {
        "Missing information requested": "missing_information",
        "Referral recategorised": "recategorisation",
        "Clinical team reassigned": "reassignment",
        "Scheduling failed": "failed_scheduling",
        "Referral cancelled": "cancellation",
        "Referral rejected": "rejection",
    }
    for activity, marker in mapping.items():
        if activity in activities:
            markers.append(marker)
    if not any(
        activity.startswith("Referral ")
        and activity
        in {
            "Referral completed",
            "Referral cancelled",
            "Referral rejected",
            "Referral closed other",
        }
        for activity in activities
    ):
        markers.append("open_or_stuck")
    if len(set(activities)) < len(activities):
        markers.append("repeated_activity")
    return tuple(markers)


def _metric_values(members: list[CaseMetrics], metric: MetricName) -> list[float]:
    return [
        float(value)
        for case in members
        if (value := case.metrics[metric].value) is not None and not isinstance(value, bool)
    ]


def build_variants(
    process_log: ProcessLog,
    case_metrics: tuple[CaseMetrics, ...],
    config: ProcessMiningConfig,
    conformance_by_case: dict[
        UUID, tuple[float | None, float | None, bool | None, bool | None]
    ]
    | None = None,
) -> tuple[ProcessVariant, ...]:
    metrics_by_case = {case.case_id: case for case in case_metrics}
    grouped: dict[tuple[str, ...], list[UUID]] = defaultdict(list)
    for trace in process_log.traces:
        grouped[trace.activities].append(trace.case_id)
    variants = []
    for activities, raw_case_ids in grouped.items():
        case_ids = tuple(sorted(raw_case_ids, key=lambda case_id: case_id.hex))
        members = [metrics_by_case[case_id] for case_id in case_ids]
        durations = [
            float(value)
            for case in members
            if (value := case.metrics[MetricName.CASE_DURATION].value) is not None
            and case.metrics[MetricName.CASE_DURATION].status.value == "calculated"
            and not isinstance(value, bool)
        ]

        first_pass = [
            value
            for case in members
            if isinstance((value := case.metrics[MetricName.FIRST_PASS_COMPLETE].value), bool)
        ]
        strict_values: list[float] = []
        governed_values: list[float] = []
        strict_full_values: list[bool] = []
        governed_full_values: list[bool] = []
        if conformance_by_case is not None:
            for case_id in case_ids:
                strict, governed, strict_full, governed_full = conformance_by_case.get(
                    case_id, (None, None, None, None)
                )
                if strict is not None:
                    strict_values.append(strict)
                if governed is not None:
                    governed_values.append(governed)
                if strict_full is not None:
                    strict_full_values.append(strict_full)
                if governed_full is not None:
                    governed_full_values.append(governed_full)
        conformance = (
            VariantConformanceSummary(
                strict_mean_fitness=fmean(strict_values) if strict_values else None,
                governed_mean_fitness=fmean(governed_values) if governed_values else None,
                strict_fully_conforming_rate=(
                    sum(strict_full_values) / len(strict_full_values)
                    if strict_full_values
                    else None
                ),
                governed_fully_conforming_rate=(
                    sum(governed_full_values) / len(governed_full_values)
                    if governed_full_values
                    else None
                ),
            )
            if conformance_by_case is not None
            else None
        )
        count = len(case_ids)
        classification = (
            VariantClassification.RARE
            if count <= config.rare_variant_case_threshold
            else VariantClassification.COMMON
            if count >= config.minimum_variant_frequency
            else VariantClassification.UNCOMMON
        )
        variants.append(
            ProcessVariant(
                variant_id=variant_id(activities, process_log.activity_mapping_version),
                activities=activities,
                case_count=count,
                case_percentage=count / len(process_log.traces),
                outcome_distribution=dict(
                    sorted(Counter(case.lifecycle_status for case in members).items())
                ),
                duration_hours=numeric_summary(durations, config.duration_percentiles),
                mean_manual_touches=(
                    fmean(_metric_values(members, MetricName.MANUAL_TOUCHES)) if members else None
                ),
                mean_handoffs=fmean(_metric_values(members, MetricName.HANDOFFS))
                if members
                else None,
                mean_rework_count=(
                    fmean(_metric_values(members, MetricName.REWORK_COUNT)) if members else None
                ),
                first_pass_completeness_rate=(
                    sum(first_pass) / len(first_pass) if first_pass else None
                ),
                service_line_distribution=dict(
                    sorted(Counter(case.service_line for case in members).items())
                ),
                referral_source_distribution=dict(
                    sorted(Counter(case.referral_source for case in members).items())
                ),
                representative_case_ids=case_ids[:10],
                conformance=conformance,
                classification=classification,
                markers=variant_markers(activities),
            )
        )
    return tuple(sorted(variants, key=lambda item: (-item.case_count, item.variant_id)))


def calculate_complexity(
    process_log: ProcessLog,
    variants: tuple[ProcessVariant, ...],
    transition_count: int,
    case_metrics: tuple[CaseMetrics, ...],
) -> ProcessComplexity:
    total = len(process_log.traces)
    lengths = [len(trace.events) for trace in process_log.traces]
    case_metrics_by_id = {case.case_id: case for case in case_metrics}
    probabilities = [variant.case_count / total for variant in variants]
    terminal_sequences = {trace.events[-1].activity for trace in process_log.traces if trace.events}
    loop_cases = sum(
        len(set(trace.activities)) < len(trace.activities) for trace in process_log.traces
    )
    rework_cases = sum(
        float(case.metrics[MetricName.REWORK_COUNT].value or 0) > 0
        for case in case_metrics_by_id.values()
    )
    handoff_cases = sum(
        float(case.metrics[MetricName.HANDOFFS].value or 0) > 0
        for case in case_metrics_by_id.values()
    )

    def coverage(count: int) -> float:
        return sum(variant.case_count for variant in variants[:count]) / total

    return ProcessComplexity(
        distinct_activity_count=len(
            {event.activity for trace in process_log.traces for event in trace.events}
        ),
        distinct_transition_count=transition_count,
        distinct_variant_count=len(variants),
        top_1_variant_coverage=coverage(1),
        top_5_variant_coverage=coverage(5),
        top_10_variant_coverage=coverage(10),
        long_tail_variant_count=sum(
            variant.classification is VariantClassification.RARE for variant in variants
        ),
        mean_activities_per_case=fmean(lengths),
        median_activities_per_case=median(lengths),
        maximum_activities_per_case=max(lengths),
        loop_case_rate=loop_cases / total,
        rework_case_rate=rework_cases / total,
        handoff_case_rate=handoff_cases / total,
        terminal_path_diversity=len(terminal_sequences),
        variant_entropy_bits=-sum(
            probability * math.log2(probability) for probability in probabilities
        ),
    )
