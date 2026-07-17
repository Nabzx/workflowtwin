"""Compatibility validation and canonical cross-artifact evidence references."""

import hashlib
from collections import Counter

from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.models import (
    EvidenceConfidence,
    EvidenceDirection,
    EvidenceReference,
    EvidenceSourceType,
    OpportunityAnalysisInput,
    ResearchContradiction,
)
from workflowtwin.opportunities.research import research_pack_fingerprint


def _evidence_id(source_type: EvidenceSourceType, record_id: str, metric: str) -> str:
    identity = f"{source_type.value}\x1f{record_id}\x1f{metric}"
    return f"evidence-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"


def _direction(value: float | None, baseline: float | None = None) -> EvidenceDirection:
    if value is None:
        return EvidenceDirection.NOT_APPLICABLE
    if baseline is None:
        return EvidenceDirection.PRESENT
    return EvidenceDirection.ELEVATED if value >= baseline else EvidenceDirection.LOWER


def validate_input_compatibility(
    analysis_input: OpportunityAnalysisInput, config: OpportunityConfig
) -> None:
    baseline = analysis_input.baseline
    process = analysis_input.process
    if baseline.analysis_version != config.expected_baseline_version:
        raise ValueError(f"unsupported baseline analysis version: {baseline.analysis_version}")
    if process.analysis_version != config.expected_process_version:
        raise ValueError(f"unsupported process analysis version: {process.analysis_version}")
    if baseline.event_schema_version != config.expected_event_schema_version:
        raise ValueError("baseline event schema version is not supported")
    if process.activity_mapping_version != config.expected_activity_map_version:
        raise ValueError("process activity-map version is not supported")
    if tuple(process.reference_model_versions) != config.expected_reference_models:
        raise ValueError("process reference-model versions are not supported")
    if baseline.source_dataset_fingerprint != process.source_dataset_fingerprint:
        raise ValueError("baseline and process analyses use different dataset fingerprints")
    if (
        process.baseline_analysis_fingerprint is not None
        and process.baseline_analysis_fingerprint != baseline.analysis_fingerprint
    ):
        raise ValueError("process analysis references a different baseline fingerprint")
    if baseline.generation_run_id != process.generation_run_id:
        raise ValueError("baseline and process generation runs do not match")
    if analysis_input.manifest is not None:
        if analysis_input.manifest.dataset_fingerprint != baseline.source_dataset_fingerprint:
            raise ValueError("manifest fingerprint does not match opportunity inputs")
        if analysis_input.manifest.generation_run_id != baseline.generation_run_id:
            raise ValueError("manifest generation run does not match opportunity inputs")
        if analysis_input.manifest.schema_version != config.expected_event_schema_version:
            raise ValueError("manifest schema version is not supported")
    if (
        analysis_input.ground_truth is not None
        and analysis_input.ground_truth.run_id != baseline.generation_run_id
    ):
        raise ValueError("ground truth generation run does not match opportunity inputs")
    if analysis_input.research.pack_version != config.expected_research_pack_version:
        raise ValueError(
            f"unsupported research pack version: {analysis_input.research.pack_version}"
        )


def _baseline_evidence(analysis_input: OpportunityAnalysisInput) -> list[EvidenceReference]:
    baseline = analysis_input.baseline
    fingerprint = baseline.analysis_fingerprint
    references = []
    for finding in baseline.findings:
        references.append(
            EvidenceReference(
                evidence_id=_evidence_id(
                    EvidenceSourceType.BASELINE_FINDING,
                    finding.finding_id,
                    finding.metric_name,
                ),
                source_type=EvidenceSourceType.BASELINE_FINDING,
                source_artifact_fingerprint=fingerprint,
                source_record_id=finding.finding_id,
                metric_or_observation=finding.metric_name,
                cohort_dimension=finding.cohort_dimension,
                cohort_value=finding.cohort_value,
                observed_value=finding.observed_value,
                unit=(
                    "rate"
                    if finding.metric_name.endswith("_rate")
                    else "hours"
                    if "hours" in finding.metric_name
                    else "count_per_case"
                ),
                sample_size=finding.cohort_size,
                direction=_direction(finding.observed_value, finding.baseline_value),
                materiality=finding.materiality.value,
                confidence=EvidenceConfidence.HIGH,
                warnings=finding.caveats,
                source_pointer=f"baseline.findings[{finding.finding_id}]",
            )
        )
    for cohort in (baseline.overall, *baseline.cohorts):
        record_id = f"{cohort.dimension}:{cohort.value}"
        for metric, rate in sorted(cohort.rates.items()):
            references.append(
                EvidenceReference(
                    evidence_id=_evidence_id(EvidenceSourceType.COHORT_METRIC, record_id, metric),
                    source_type=EvidenceSourceType.COHORT_METRIC,
                    source_artifact_fingerprint=fingerprint,
                    source_record_id=record_id,
                    metric_or_observation=metric,
                    cohort_dimension=cohort.dimension,
                    cohort_value=cohort.value,
                    observed_value=rate.value,
                    unit="rate",
                    sample_size=rate.denominator,
                    direction=_direction(rate.value),
                    materiality=None,
                    confidence=(
                        EvidenceConfidence.HIGH
                        if rate.value is not None
                        else EvidenceConfidence.LOW
                    ),
                    warnings=() if rate.value is not None else ("metric unavailable",),
                    source_pointer=f"baseline.cohorts[{record_id}].rates[{metric}]",
                )
            )
        for metric, summary in sorted(cohort.summaries.items()):
            references.append(
                EvidenceReference(
                    evidence_id=_evidence_id(EvidenceSourceType.COHORT_METRIC, record_id, metric),
                    source_type=EvidenceSourceType.COHORT_METRIC,
                    source_artifact_fingerprint=fingerprint,
                    source_record_id=record_id,
                    metric_or_observation=metric,
                    cohort_dimension=cohort.dimension,
                    cohort_value=cohort.value,
                    observed_value=summary.mean,
                    unit=("hours" if "hours" in metric else "count_per_case"),
                    sample_size=summary.available_count,
                    direction=_direction(summary.mean),
                    materiality=None,
                    confidence=(
                        EvidenceConfidence.HIGH
                        if summary.mean is not None
                        else EvidenceConfidence.LOW
                    ),
                    warnings=() if summary.mean is not None else ("metric unavailable",),
                    source_pointer=f"baseline.cohorts[{record_id}].summaries[{metric}]",
                )
            )
    for metric, value in (
        ("delayed_ingestion_cases", baseline.quality.delayed_ingestion_cases),
        ("out_of_order_ingestion_cases", baseline.quality.out_of_order_ingestion_cases),
        ("unsupported_schema_cases", baseline.quality.unsupported_schema_cases),
    ):
        references.append(
            EvidenceReference(
                evidence_id=_evidence_id(EvidenceSourceType.BASELINE_QUALITY, "quality", metric),
                source_type=EvidenceSourceType.BASELINE_QUALITY,
                source_artifact_fingerprint=fingerprint,
                source_record_id="quality",
                metric_or_observation=metric,
                cohort_dimension=None,
                cohort_value=None,
                observed_value=value,
                unit="cases",
                sample_size=baseline.case_count,
                direction=_direction(float(value)),
                materiality=None,
                confidence=EvidenceConfidence.HIGH,
                warnings=baseline.quality.data_validation_warnings,
                source_pointer=f"baseline.quality.{metric}",
            )
        )
    return references


def _process_evidence(analysis_input: OpportunityAnalysisInput) -> list[EvidenceReference]:
    process = analysis_input.process
    fingerprint = process.process_analysis_fingerprint
    references = []
    for candidate in process.bottleneck_candidates:
        references.append(
            EvidenceReference(
                evidence_id=_evidence_id(
                    EvidenceSourceType.PROCESS_CANDIDATE,
                    candidate.candidate_id,
                    candidate.candidate_type,
                ),
                source_type=EvidenceSourceType.PROCESS_CANDIDATE,
                source_artifact_fingerprint=fingerprint,
                source_record_id=candidate.candidate_id,
                metric_or_observation=candidate.candidate_type,
                cohort_dimension=candidate.cohort_dimension,
                cohort_value=candidate.cohort_value,
                observed_value=candidate.frequency,
                unit="occurrences",
                sample_size=candidate.case_count,
                direction=EvidenceDirection.ELEVATED,
                materiality=candidate.materiality.value,
                confidence=EvidenceConfidence.HIGH,
                warnings=candidate.warnings,
                source_pointer=f"process.bottleneck_candidates[{candidate.candidate_id}]",
            )
        )
    for transition in process.transition_statistics:
        references.append(
            EvidenceReference(
                evidence_id=_evidence_id(
                    EvidenceSourceType.PROCESS_TRANSITION,
                    transition.transition_id,
                    "median_elapsed_hours",
                ),
                source_type=EvidenceSourceType.PROCESS_TRANSITION,
                source_artifact_fingerprint=fingerprint,
                source_record_id=transition.transition_id,
                metric_or_observation=(
                    f"{transition.source_activity} -> {transition.target_activity}"
                ),
                cohort_dimension=None,
                cohort_value=None,
                observed_value=transition.elapsed_hours.median,
                unit="elapsed_hours",
                sample_size=transition.distinct_case_count,
                direction=_direction(transition.elapsed_hours.median),
                materiality=None,
                confidence=EvidenceConfidence.HIGH,
                warnings=transition.warnings,
                source_pointer=f"process.transition_statistics[{transition.transition_id}]",
            )
        )
    for variant in process.variants:
        if not variant.markers:
            continue
        references.append(
            EvidenceReference(
                evidence_id=_evidence_id(
                    EvidenceSourceType.PROCESS_VARIANT, variant.variant_id, "markers"
                ),
                source_type=EvidenceSourceType.PROCESS_VARIANT,
                source_artifact_fingerprint=fingerprint,
                source_record_id=variant.variant_id,
                metric_or_observation=",".join(variant.markers),
                cohort_dimension=None,
                cohort_value=None,
                observed_value=variant.case_count,
                unit="cases",
                sample_size=variant.case_count,
                direction=EvidenceDirection.PRESENT,
                materiality=variant.classification.value,
                confidence=EvidenceConfidence.HIGH,
                warnings=(),
                source_pointer=f"process.variants[{variant.variant_id}]",
            )
        )
    for category, count in sorted(process.deviation_summary.items()):
        references.append(
            EvidenceReference(
                evidence_id=_evidence_id(EvidenceSourceType.PROCESS_DEVIATION, category, "count"),
                source_type=EvidenceSourceType.PROCESS_DEVIATION,
                source_artifact_fingerprint=fingerprint,
                source_record_id=category,
                metric_or_observation=category,
                cohort_dimension=None,
                cohort_value=None,
                observed_value=count,
                unit="cases_or_occurrences",
                sample_size=process.case_count,
                direction=EvidenceDirection.PRESENT,
                materiality=None,
                confidence=EvidenceConfidence.MODERATE,
                warnings=("deviation counts can include occurrences rather than unique cases",),
                source_pointer=f"process.deviation_summary[{category}]",
            )
        )
    for metric, value in (
        ("duplicate_events_excluded", process.log_quality.duplicate_events_excluded),
        ("out_of_order_ingestion_cases", process.log_quality.out_of_order_ingestion_cases),
        ("unsupported_mapping_count", process.log_quality.unsupported_mapping_count),
    ):
        references.append(
            EvidenceReference(
                evidence_id=_evidence_id(EvidenceSourceType.PROCESS_QUALITY, "quality", metric),
                source_type=EvidenceSourceType.PROCESS_QUALITY,
                source_artifact_fingerprint=fingerprint,
                source_record_id="quality",
                metric_or_observation=metric,
                cohort_dimension=None,
                cohort_value=None,
                observed_value=value,
                unit="cases_or_events",
                sample_size=process.case_count,
                direction=_direction(float(value)),
                materiality=None,
                confidence=EvidenceConfidence.HIGH,
                warnings=process.log_quality.warnings,
                source_pointer=f"process.log_quality.{metric}",
            )
        )
    return references


def _research_evidence(
    analysis_input: OpportunityAnalysisInput,
) -> tuple[list[EvidenceReference], list[ResearchContradiction]]:
    pack = analysis_input.research
    fingerprint = research_pack_fingerprint(pack)
    references = []
    observation_by_id = {
        observation.observation_id: observation
        for session in pack.sessions
        for observation in session.observations
    }
    evidence_by_observation = {}
    for session in pack.sessions:
        for observation in session.observations:
            evidence_id = _evidence_id(
                EvidenceSourceType.RESEARCH_OBSERVATION,
                observation.observation_id,
                observation.reported_problem,
            )
            evidence_by_observation[observation.observation_id] = evidence_id
            references.append(
                EvidenceReference(
                    evidence_id=evidence_id,
                    source_type=EvidenceSourceType.RESEARCH_OBSERVATION,
                    source_artifact_fingerprint=fingerprint,
                    source_record_id=observation.observation_id,
                    metric_or_observation=observation.reported_problem,
                    cohort_dimension=observation.cohort_dimension,
                    cohort_value=observation.cohort_value,
                    observed_value=observation.frequency.value,
                    unit="reported_frequency",
                    sample_size=1,
                    direction=EvidenceDirection.MIXED
                    if observation.contradicts
                    else EvidenceDirection.PRESENT,
                    materiality=observation.severity.value,
                    confidence=EvidenceConfidence.MODERATE,
                    warnings=("fictional participant report; not an operational measurement",),
                    source_pointer=(
                        f"research.sessions[{session.session_id}].observations"
                        f"[{observation.observation_id}]"
                    ),
                )
            )
    contradictions = []
    seen_pairs: set[tuple[str, str]] = set()
    for observation in observation_by_id.values():
        for target_id in observation.contradicts:
            pair_values = sorted((observation.observation_id, target_id))
            pair = (pair_values[0], pair_values[1])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            identity = "\x1f".join(pair)
            contradictions.append(
                ResearchContradiction(
                    contradiction_id=(
                        f"contradiction-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"
                    ),
                    evidence_ids=tuple(evidence_by_observation[item] for item in pair),
                    nature=(
                        "fictional participants disagree about autonomy, exceptions, or controls"
                    ),
                    affected_dimensions=("readiness", "risk", "confidence"),
                    unresolved_question=(
                        "Which administrative cases can be handled by explicit rules without "
                        "hiding legitimate exceptions?"
                    ),
                    future_discovery_need=(
                        "Observe exception handling and test a recommendation-only workflow."
                    ),
                )
            )
    return references, contradictions


def build_evidence_registry(
    analysis_input: OpportunityAnalysisInput,
) -> tuple[tuple[EvidenceReference, ...], tuple[ResearchContradiction, ...]]:
    research, contradictions = _research_evidence(analysis_input)
    references = [
        *_baseline_evidence(analysis_input),
        *_process_evidence(analysis_input),
        *research,
    ]
    identifiers = Counter(item.evidence_id for item in references)
    duplicate = next((item for item, count in identifiers.items() if count > 1), None)
    if duplicate is not None:
        raise ValueError(f"evidence identifiers must be unique: {duplicate}")
    return (
        tuple(sorted(references, key=lambda item: item.evidence_id)),
        tuple(sorted(contradictions, key=lambda item: item.contradiction_id)),
    )
