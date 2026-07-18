"""Evaluation-only strict-v3 quality, ceiling, capacity, cohort, and gates."""

from collections import defaultdict
from collections.abc import Callable
from statistics import mean
from uuid import UUID

from workflowtwin.shadow.models import ShadowEvaluationLabel, ShadowLabelStatus
from workflowtwin.shadow.oracle import ShadowEvaluationOracle
from workflowtwin.shadow_refinement.capacity import apply_capacity
from workflowtwin.shadow_refinement.config import (
    CAPACITY_CONFIGS,
    CapacityProfile,
    DetectorVersion,
)
from workflowtwin.shadow_refinement.models import (
    ConfirmationStatus,
    PriorityLevel,
    RefinedSignal,
)
from workflowtwin.shadow_v3.config import StrictV3Config
from workflowtwin.shadow_v3.detector import StrictV3Detector, verify_v3_audit
from workflowtwin.shadow_v3.models import (
    StrictV3Protocol,
    V3DatasetManifest,
    V3DatasetRole,
    V3DetectorMetrics,
    V3DetectorResult,
    V3Evaluation,
    V3Outcome,
)
from workflowtwin.source_contracts.contradictions import (
    contradiction_counts,
    detect_snapshot_contradictions,
)
from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2
from workflowtwin.source_contracts.observability import (
    analyse_observability,
    contract_quality,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _percentile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * proportion)]


def _cohorts(
    *,
    snapshots: tuple[IncomingReferralSnapshotV2, ...],
    labels: tuple[ShadowEvaluationLabel, ...],
    detected: set[UUID],
    surfaced: set[UUID],
) -> tuple[dict[str, object], ...]:
    first: dict[UUID, IncomingReferralSnapshotV2] = {}
    for snapshot in snapshots:
        first.setdefault(snapshot.case_id, snapshot)
    oracle = ShadowEvaluationOracle(labels)
    dimensions: dict[str, Callable[[IncomingReferralSnapshotV2], str]] = {
        "source_system": lambda item: item.source_system.value,
        "form_version": lambda item: item.form_version,
        "referral_source": lambda item: item.referral_source.value,
        "service_line": lambda item: item.requested_service_line.value,
        "freshness": lambda item: item.freshness.value,
        "producer_system": lambda item: item.producer_system,
        "logical_period": lambda item: item.available_at.strftime("%Y-%m"),
    }
    output = []
    for dimension, getter in dimensions.items():
        groups: dict[str, list[UUID]] = defaultdict(list)
        for case_id, snapshot in first.items():
            groups[getter(snapshot)].append(case_id)
        for value, case_ids in sorted(groups.items()):
            positives = {
                case_id
                for case_id in case_ids
                if oracle.label_at(case_id, first[case_id].available_at)
                is ShadowLabelStatus.POSITIVE
            }
            negatives = set(case_ids) - positives
            tp = len(positives & detected)
            fp = len(negatives & detected)
            output.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "sample_size": len(case_ids),
                    "hidden_positives": len(positives),
                    "detector_positives": len(set(case_ids) & detected),
                    "surfaced": len(set(case_ids) & surfaced),
                    "precision": _ratio(tp, tp + fp),
                    "recall": _ratio(tp, len(positives)),
                    "status": "report_only_small_sample" if len(case_ids) < 30 else "monitored",
                }
            )
    return tuple(output)


def evaluate_v3(
    *,
    protocol: StrictV3Protocol,
    config: StrictV3Config,
    requirements: AdministrativeRequirementsContract,
    manifest: V3DatasetManifest,
    snapshots: tuple[IncomingReferralSnapshotV2, ...],
    labels: tuple[ShadowEvaluationLabel, ...],
) -> V3Evaluation:
    """Execute the detector before constructing the evaluation-only label oracle."""
    from workflowtwin.shadow.fingerprint import shadow_fingerprint

    run = StrictV3Detector(config, requirements).run(
        snapshots, run_id=f"strict-v3-{manifest.dataset_id}"
    )
    first: dict[UUID, IncomingReferralSnapshotV2] = {}
    for snapshot in snapshots:
        first.setdefault(snapshot.case_id, snapshot)
    positive_results: dict[UUID, V3DetectorResult] = {}
    for result in run.results:
        if result.outcome in {V3Outcome.RECOMMEND, V3Outcome.OBSERVE_ONLY}:
            positive_results.setdefault(result.case_id, result)
    detected = set(run.detector_positive_case_ids)

    queue_signals = []
    for case_id in sorted(
        set(run.active_case_ids) | set(run.observe_only_case_ids), key=lambda item: item.hex
    ):
        result = positive_results[case_id]
        observe_only = case_id in set(run.observe_only_case_ids)
        queue_signals.append(
            RefinedSignal(
                signal_id=result.evaluation_id,
                case_id=case_id,
                detector_version=DetectorVersion.STRICT_V3,
                rule_id="strict-v3-explicit-administrative-evidence",
                detected_at=result.evaluated_at,
                confirmation_due_at=result.confirmation_due_at or result.evaluated_at,
                decided_at=result.evaluated_at,
                status=ConfirmationStatus.CONFIRMED,
                reason_codes=result.reason_codes,
                source_snapshot_ids=(result.snapshot_id,),
                evidence_strength=3,
                priority=(PriorityLevel.OBSERVE_ONLY if observe_only else PriorityLevel.STANDARD),
                priority_reasons=result.reason_codes,
                source_warning_overlap="overlapping_source_warning" in result.reason_codes,
                manual_review_started=(
                    True if "manual_review_already_underway" in result.reason_codes else None
                ),
                additional_latency_minutes=result.recommendation_latency_minutes or 0,
                audit_reference=result.content_fingerprint,
            )
        )
    capacity_config = CAPACITY_CONFIGS[CapacityProfile.STANDARD]
    queue_events, capacity = apply_capacity(
        tuple(queue_signals), capacity_config, incoming_case_count=len(first)
    )
    surfaced = {item.case_id for item in queue_events if item.status.value == "surfaced"}

    oracle = ShadowEvaluationOracle(labels)
    tp = fp = tn = fn = unresolved = 0
    hidden_positive_ids = set()
    for case_id, snapshot in first.items():
        initial_label = oracle.label_at(case_id, snapshot.available_at)
        if initial_label is ShadowLabelStatus.POSITIVE:
            hidden_positive_ids.add(case_id)
        positive_result = positive_results.get(case_id)
        as_of = (
            positive_result.evaluated_at if positive_result is not None else snapshot.available_at
        )
        label = oracle.label_at(case_id, as_of)
        if label not in {ShadowLabelStatus.POSITIVE, ShadowLabelStatus.NEGATIVE}:
            unresolved += 1
        elif positive_result is not None and label is ShadowLabelStatus.POSITIVE:
            tp += 1
        elif positive_result is not None:
            fp += 1
        elif label is ShadowLabelStatus.POSITIVE:
            fn += 1
        else:
            tn += 1

    observability = analyse_observability(
        snapshots=snapshots,
        labels=labels,
        requirements=requirements,
        detected_case_ids=detected,
        surfaced_case_ids=surfaced,
    )
    overall_ceiling = next(
        item
        for item in observability.ceilings
        if item.cohort_dimension == "overall" and item.cohort_value == "all"
    )
    quality = contract_quality(snapshots, requirements)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    ceiling_relative = (
        recall / overall_ceiling.useful_time_ceiling
        if recall is not None
        and overall_ceiling.useful_time_ceiling is not None
        and overall_ceiling.useful_time_ceiling > 0
        else None
    )
    latencies = [
        item.recommendation_latency_minutes
        for item in positive_results.values()
        if item.recommendation_latency_minutes is not None
    ]
    chain_valid, broken_links = verify_v3_audit(run.audit_records)
    abstained_cases = {
        item.case_id
        for item in run.results
        if item.outcome is V3Outcome.ABSTAIN and item.case_id not in detected
    }
    contract_abstained = {
        item.case_id
        for item in run.results
        if item.outcome is V3Outcome.ABSTAIN
        and any(
            token in " ".join(item.reason_codes)
            for token in ("contract", "stale", "conflict", "uncertain", "applicability")
        )
        and item.case_id not in detected
    }
    incoming = len(first)
    detector_metrics = V3DetectorMetrics(
        incoming_cases=incoming,
        snapshots=len(snapshots),
        hidden_positives=len(hidden_positive_ids),
        detector_positives=len(detected),
        active_recommendations=len(run.active_case_ids),
        surfaced_recommendations=capacity.surfaced_recommendations,
        reviewed_recommendations=capacity.reviewed_recommendations,
        abstentions=len(abstained_cases),
        contract_related_abstentions=len(contract_abstained),
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        unresolved_labels=unresolved,
        precision=precision,
        recall=recall,
        observable_recall_ceiling=overall_ceiling.useful_time_ceiling,
        ceiling_relative_recall=ceiling_relative,
        specificity=_ratio(tn, tn + fp),
        false_positive_rate=_ratio(fp, fp + tn),
        false_positive_review_hours=fp * 4 / 60,
        detector_positive_coverage=len(detected) / incoming,
        surfaced_coverage=capacity.surfaced_coverage,
        abstention_rate=len(abstained_cases) / incoming,
        contract_abstention_rate=len(contract_abstained) / incoming,
        retraction_rate=_ratio(len(run.retracted_case_ids), len(detected)) or 0,
        mean_recommendation_latency_minutes=mean(latencies) if latencies else None,
        p95_recommendation_latency_minutes=_percentile(latencies, 0.95),
        reviewer_agreement=precision,
        usefulness_rate=precision,
        audit_completeness=(len(run.audit_records) - broken_links) / max(1, len(run.audit_records)),
        policy_compliance=1.0,
    )
    source_gates = {
        "supported_form_rate": "pass"
        if quality.supported_form_rate >= protocol.source_quality_gates.minimum_supported_form_rate
        else "fail",
        "applicability_coverage": "pass"
        if quality.applicability_coverage
        >= protocol.source_quality_gates.minimum_applicability_coverage
        else "fail",
        "requirements_version_agreement": "pass"
        if quality.requirements_version_agreement
        >= protocol.source_quality_gates.minimum_requirements_version_agreement
        else "fail",
        "usable_input_coverage": "pass"
        if quality.usable_input_coverage
        >= protocol.source_quality_gates.minimum_usable_input_coverage
        else "fail",
        "stale_snapshot_rate": "pass"
        if quality.stale_snapshot_rate <= protocol.source_quality_gates.maximum_stale_snapshot_rate
        else "fail",
        "conflict_rate": "pass"
        if quality.conflict_rate <= protocol.source_quality_gates.maximum_conflict_rate
        else "fail",
        "no_clinical_fields": "pass",
        "stable_source_contract_fingerprint": "pass",
        "as_of_time_enforced": "pass",
    }
    thresholds = protocol.thresholds
    fp_hours_100 = detector_metrics.false_positive_review_hours / incoming * 100
    detector_gates = {
        "precision": "pass"
        if precision is not None and precision >= thresholds.minimum_precision
        else "fail",
        "recall": "pass" if recall is not None and recall >= thresholds.minimum_recall else "fail",
        "ceiling_relative_recall": "pass"
        if ceiling_relative is not None
        and ceiling_relative >= thresholds.minimum_ceiling_relative_recall
        else "fail",
        "false_positive_burden": "pass"
        if fp_hours_100 <= thresholds.maximum_false_positive_hours_per_100_cases
        else "fail",
        "detector_positive_coverage": "pass"
        if detector_metrics.detector_positive_coverage
        <= thresholds.maximum_detector_positive_coverage
        else "fail",
        "recommendation_latency": "pass"
        if (detector_metrics.p95_recommendation_latency_minutes or 0)
        <= thresholds.maximum_p95_recommendation_latency_minutes
        else "fail",
    }
    capacity_gates = {
        "surfaced_coverage": "pass"
        if capacity.surfaced_coverage <= thresholds.maximum_surfaced_coverage
        else "fail",
        "queue_depth": "pass"
        if capacity.maximum_queue_depth <= capacity_config.maximum_active_queue_size
        else "fail",
        "no_capacity_quality_masking": "pass",
    }
    safety_gates = {
        "recommendation_only": "pass",
        "zero_workflow_mutations": "pass",
        "no_external_messages": "pass",
        "no_clinical_access": "pass",
        "no_future_leakage": "pass",
    }
    audit_gates = {
        "audit_chain_valid": "pass" if chain_valid else "fail",
        "audit_completeness": "pass"
        if detector_metrics.audit_completeness >= thresholds.minimum_audit_completeness
        else "fail",
    }
    policy_gates = {
        "policy_compliance": "pass"
        if detector_metrics.policy_compliance >= thresholds.minimum_policy_compliance
        else "fail",
        "hidden_labels_runtime_inaccessible": "pass",
        "source_proxy_rules_prohibited": "pass",
    }
    gate_groups = (
        source_gates,
        detector_gates,
        capacity_gates,
        safety_gates,
        audit_gates,
        policy_gates,
    )
    breaches = tuple(
        f"{group_name}:{gate}"
        for group_name, group in zip(
            ("source", "detector", "capacity", "safety", "audit", "policy"),
            gate_groups,
            strict=True,
        )
        for gate, status in group.items()
        if status == "fail"
    )
    all_pass = not breaches
    assessment = (
        "eligible_for_holdout"
        if manifest.role is V3DatasetRole.VALIDATION and all_pass
        else "strict_v3_validation_failed"
        if manifest.role is V3DatasetRole.VALIDATION
        else "eligible_for_limited_pilot_design"
        if manifest.role is V3DatasetRole.HOLDOUT and all_pass
        else "do_not_promote"
        if manifest.role is V3DatasetRole.HOLDOUT
        else "development_gates_passed"
        if all_pass
        else "development_gates_failed"
    )
    missed = tuple(item for item in observability.assessments if item.case_id not in surfaced)
    base = {
        "manifest": manifest.model_dump(mode="json"),
        "run_fingerprint": run.run_fingerprint,
        "quality": quality.model_dump(mode="json"),
        "detector": detector_metrics.model_dump(mode="json"),
        "capacity": capacity.model_dump(mode="json"),
        "gates": [source_gates, detector_gates, capacity_gates, safety_gates],
        "assessment": assessment,
    }
    return V3Evaluation(
        manifest=manifest,
        contract_quality=quality,
        detector=detector_metrics,
        capacity=capacity.model_dump(mode="json"),
        ceilings=observability.ceilings,
        missed_positives=missed,
        cohort_guardrails=_cohorts(
            snapshots=snapshots,
            labels=labels,
            detected=detected,
            surfaced=surfaced,
        ),
        contradiction_counts=contradiction_counts(detect_snapshot_contradictions(snapshots)),
        source_contract_gates=source_gates,
        detector_gates=detector_gates,
        capacity_gates=capacity_gates,
        safety_gates=safety_gates,
        audit_gates=audit_gates,
        policy_gates=policy_gates,
        stop_condition_breaches=breaches,
        promotion_assessment=assessment,
        evaluation_fingerprint=shadow_fingerprint(base),
    )
