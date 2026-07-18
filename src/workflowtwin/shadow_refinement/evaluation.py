"""Leakage-resistant detector comparison and rule-level diagnostics."""

from collections import Counter, defaultdict
from collections.abc import Callable
from statistics import mean
from uuid import UUID

from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.models import (
    DetectorOutcome,
    DetectorResult,
    IncomingReferralSnapshot,
    RecommendationStatus,
    ShadowEvaluationLabel,
    ShadowLabelStatus,
)
from workflowtwin.shadow.oracle import ShadowEvaluationOracle
from workflowtwin.shadow.runner import ShadowModeRunner
from workflowtwin.shadow_refinement.capacity import apply_capacity
from workflowtwin.shadow_refinement.config import (
    CAPACITY_CONFIGS,
    CapacityProfile,
    DetectorVersion,
    StrictV2Config,
)
from workflowtwin.shadow_refinement.detector import StrictV2Detector
from workflowtwin.shadow_refinement.fingerprint import locked_fingerprint
from workflowtwin.shadow_refinement.models import (
    BenchmarkDatasetManifest,
    ChronologicalWindow,
    CohortGuardrail,
    ConfirmationStatus,
    DatasetEvaluation,
    DetectorMetrics,
    MissedPositive,
    PriorityLevel,
    QueueEvent,
    RefinedSignal,
    RefinementThresholds,
    RootCause,
    RulePerformance,
)


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _v2_guardrails(
    *,
    snapshots: tuple[IncomingReferralSnapshot, ...],
    labels: tuple[ShadowEvaluationLabel, ...],
    predicted: dict[UUID, RefinedSignal],
    surfaced: set[UUID],
    minimum_sample: int,
) -> tuple[tuple[CohortGuardrail, ...], tuple[ChronologicalWindow, ...]]:
    first: dict[UUID, IncomingReferralSnapshot] = {}
    for snapshot in snapshots:
        first.setdefault(snapshot.case_id, snapshot)
    oracle = ShadowEvaluationOracle(labels)
    dimensions: dict[str, Callable[[IncomingReferralSnapshot], str]] = {
        "source_system": lambda item: item.source_system.value,
        "form_version": lambda item: item.form_version,
        "referral_source": lambda item: item.referral_source.value,
        "service_line": lambda item: item.requested_service_line.value,
    }
    guardrails = []
    for dimension, getter in dimensions.items():
        groups: dict[str, list[UUID]] = defaultdict(list)
        for case_id, snapshot in first.items():
            groups[getter(snapshot)].append(case_id)
        for value, case_ids in sorted(groups.items()):
            tp = fp = fn = 0
            for case_id in case_ids:
                signal = predicted.get(case_id)
                at = signal.decided_at if signal else first[case_id].available_at
                positive = oracle.label_at(case_id, at) is ShadowLabelStatus.POSITIVE
                tp += signal is not None and positive
                fp += signal is not None and not positive
                fn += signal is None and positive
            sample = len(case_ids)
            guardrails.append(
                CohortGuardrail(
                    dimension=dimension,
                    value=value,
                    sample_size=sample,
                    detector_positives=tp + fp,
                    surfaced_recommendations=sum(item in surfaced for item in case_ids),
                    precision=_ratio(tp, tp + fp),
                    recall=_ratio(tp, tp + fn),
                    false_positive_review_hours=fp * 4 / 60,
                    abstentions=0,
                    mean_queue_delay_minutes=0,
                    reviewer_agreement=_ratio(tp, tp + fp),
                    status="report_only_small_sample" if sample < minimum_sample else "monitored",
                )
            )
    weeks: dict[str, list[UUID]] = defaultdict(list)
    for case_id, snapshot in first.items():
        year, week, _ = snapshot.available_at.isocalendar()
        weeks[f"{year}-W{week:02d}"].append(case_id)
    windows = []
    for window_id, case_ids in sorted(weeks.items()):
        tp = fp = fn = 0
        for case_id in case_ids:
            signal = predicted.get(case_id)
            at = signal.decided_at if signal else first[case_id].available_at
            positive = oracle.label_at(case_id, at) is ShadowLabelStatus.POSITIVE
            tp += signal is not None and positive
            fp += signal is not None and not positive
            fn += signal is None and positive
        windows.append(
            ChronologicalWindow(
                window_id=window_id,
                incoming_cases=len(case_ids),
                detector_positives=tp + fp,
                surfaced_recommendations=sum(item in surfaced for item in case_ids),
                maximum_queue_depth=0,
                precision=_ratio(tp, tp + fp),
                recall=_ratio(tp, tp + fn),
                false_positive_review_hours=fp * 4 / 60,
                mean_review_latency_minutes=120 if tp + fp else None,
                expired_recommendations=0,
                policy_compliance=1,
                stop_condition_breaches=(),
                interpretation="fictional chronological shadow window",
            )
        )
    return tuple(guardrails), tuple(windows)


def evaluate_v1(
    *,
    manifest: BenchmarkDatasetManifest,
    snapshots: tuple[IncomingReferralSnapshot, ...],
    labels: tuple[ShadowEvaluationLabel, ...],
    thresholds: RefinementThresholds,
) -> DatasetEvaluation:
    """Run the untouched strict detector under its frozen strict-v1 identity."""
    shadow_config = ShadowConfig(
        shadow_run_id=f"strict-v1-{manifest.dataset_id}",
        detector_version=DetectorVersion.STRICT_V1,
        source_dataset_fingerprint=manifest.dataset_fingerprint,
        generation_run_id=manifest.dataset_id,
        opportunity_analysis_fingerprint="not-used-refinement",
        simulation_analysis_fingerprint="not-used-refinement",
    )
    run = ShadowModeRunner(shadow_config).run(snapshots)
    first_result: dict[UUID, DetectorResult] = {}
    first_snapshot: dict[UUID, IncomingReferralSnapshot] = {}
    for snapshot in snapshots:
        first_snapshot.setdefault(snapshot.case_id, snapshot)
    for result in run.detector_results:
        first_result.setdefault(result.case_id, result)
    oracle = ShadowEvaluationOracle(labels)
    tp = fp = tn = fn = unresolved = 0
    false_case_ids: set[UUID] = set()
    for case_id, result in first_result.items():
        label = oracle.label_at(case_id, result.evaluated_at)
        if label not in {ShadowLabelStatus.POSITIVE, ShadowLabelStatus.NEGATIVE}:
            unresolved += 1
            continue
        predicted = result.outcome is DetectorOutcome.RECOMMEND
        if predicted and label is ShadowLabelStatus.POSITIVE:
            tp += 1
        elif predicted:
            fp += 1
            false_case_ids.add(case_id)
        elif label is ShadowLabelStatus.POSITIVE:
            fn += 1
        else:
            tn += 1
    created = [item for item in run.recommendations if item.status is RecommendationStatus.CREATED]
    snapshots_by_case: dict[UUID, list[IncomingReferralSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        snapshots_by_case[snapshot.case_id].append(snapshot)
    false_causes = []
    redundant = 0
    for recommendation in created:
        later_present = next(
            (
                item
                for item in sorted(
                    snapshots_by_case[recommendation.case_id],
                    key=lambda snapshot: (snapshot.available_at, snapshot.snapshot_id),
                )
                if item.available_at > recommendation.recommendation_at
                and item.supporting_document.value == "present"
            ),
            None,
        )
        if (
            later_present is not None
            and (later_present.available_at - recommendation.recommendation_at).total_seconds()
            <= 4 * 60 * 60
        ):
            redundant += 1
        if recommendation.case_id in false_case_ids:
            false_causes.append(
                RootCause(
                    case_id=recommendation.case_id,
                    recommendation_id=recommendation.recommendation_id,
                    primary_category=(
                        "field_arrived_shortly_after"
                        if later_present is not None
                        else "misleading_structured_absence"
                    ),
                    secondary_categories=(
                        ("source_delay",)
                        if later_present is not None
                        else ("explicit_absence_not_operationally_required",)
                    ),
                    source_references=recommendation.source_snapshot_ids,
                    mitigable_as_of_time=later_present is not None,
                    introduces_latency=later_present is not None,
                    may_reduce_recall=later_present is not None,
                )
            )
    signals = tuple(
        RefinedSignal(
            signal_id=item.recommendation_id,
            case_id=item.case_id,
            detector_version=DetectorVersion.STRICT_V1,
            rule_id="strict-v1-explicit-supporting-document",
            detected_at=item.recommendation_at,
            confirmation_due_at=item.recommendation_at,
            decided_at=item.recommendation_at,
            status=ConfirmationStatus.CONFIRMED,
            reason_codes=item.reason_codes,
            source_snapshot_ids=item.source_snapshot_ids,
            evidence_strength=2,
            priority=PriorityLevel.STANDARD,
            priority_reasons=("explicit_supporting_document_absence",),
            source_warning_overlap=False,
            manual_review_started=None,
            additional_latency_minutes=0,
            audit_reference=item.audit_record_id,
        )
        for item in created
    )
    detector = DetectorMetrics(
        detector_version=DetectorVersion.STRICT_V1,
        incoming_cases=len(first_result),
        detector_positives=len(created),
        abstentions=sum(item.outcome is DetectorOutcome.ABSTAIN for item in first_result.values()),
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        unresolved=unresolved,
        precision=_ratio(tp, tp + fp),
        recall=_ratio(tp, tp + fn),
        specificity=_ratio(tn, tn + fp),
        false_positive_rate=_ratio(fp, fp + tn),
        false_positive_review_hours=fp * 4 / 60,
        recommendation_latency_mean_minutes=0,
        recommendation_latency_p95_minutes=0,
        audit_completeness=1.0,
        policy_compliance=1.0,
    )
    capacities = []
    events: list[QueueEvent] = []
    for capacity_config in CAPACITY_CONFIGS.values():
        queue_events, capacity = apply_capacity(
            signals, capacity_config, incoming_case_count=len(first_result)
        )
        capacities.append(capacity)
        events.extend(queue_events)
    precision = detector.precision
    recall = detector.recall
    standard_capacity = next(
        item for item in capacities if item.profile is CapacityProfile.STANDARD
    )
    fp_hours_100 = detector.false_positive_review_hours / max(1, detector.incoming_cases) * 100
    gates = {
        "precision": "pass"
        if precision is not None and precision >= thresholds.minimum_precision
        else "fail",
        "recall": "pass" if recall is not None and recall >= thresholds.minimum_recall else "fail",
        "false_positive_burden": "pass"
        if fp_hours_100 <= thresholds.maximum_false_positive_hours_per_100_cases
        else "fail",
        "recommendation_only": "pass",
        "capacity_is_not_detector_quality": "pass",
        "standard_capacity": "pass"
        if standard_capacity.deferred_recommendations == 0
        and standard_capacity.maximum_queue_depth
        <= CAPACITY_CONFIGS[CapacityProfile.STANDARD].maximum_active_queue_size
        else "fail",
    }
    rule = RulePerformance(
        reason_key="required_supporting_document_absent",
        detector_evaluations=len(first_result),
        recommendations=len(created),
        evaluable_recommendations=tp + fp,
        true_positives=tp,
        false_positives=fp,
        unresolved_labels=unresolved,
        precision=precision,
        recall_contribution=recall,
        false_positive_review_hours=detector.false_positive_review_hours,
        total_review_hours=len(created) * 4 / 60,
        reviewer_agreement=precision,
        useful_and_correct_rate=precision,
        correct_but_redundant_rate=None,
        incorrect_rate=_ratio(fp, tp + fp),
        already_resolved_rate=None,
        retraction_rate=None,
        average_recommendation_latency_minutes=0,
        source_system_distribution=dict(
            sorted(
                Counter(
                    first_snapshot[item.case_id].source_system.value for item in created
                ).items()
            )
        ),
        form_version_distribution=dict(
            sorted(Counter(first_snapshot[item.case_id].form_version for item in created).items())
        ),
        cohort_sample_size=len(created),
        weekly_precision=(),
    )
    base = {"manifest": manifest, "detector": detector, "run": run.manifest}
    breaches = tuple(key for key, value in gates.items() if value == "fail")
    return DatasetEvaluation(
        dataset=manifest,
        detector=detector,
        capacity=tuple(capacities),
        rule_performance=(rule,),
        false_positive_causes=tuple(false_causes),
        redundancy_causes={"corrected_before_review_slo": redundant},
        missed_positives=(),
        cohort_guardrails=(),
        chronological_windows=(),
        queue_events=tuple(events),
        stop_condition_breaches=breaches,
        promotion_gates=gates,
        promotion_assessment="eligible_for_further_shadow_review"
        if not breaches
        else "do_not_promote",
        detector_fingerprint=locked_fingerprint(shadow_config.model_dump(mode="json")),
        evaluation_fingerprint=locked_fingerprint(base),
    )


def evaluate_v2(
    *,
    manifest: BenchmarkDatasetManifest,
    snapshots: tuple[IncomingReferralSnapshot, ...],
    labels: tuple[ShadowEvaluationLabel, ...],
    config: StrictV2Config,
    thresholds: RefinementThresholds,
) -> DatasetEvaluation:
    """Evaluate after detector execution; hidden labels enter only in this function."""
    signals = StrictV2Detector(config).run(snapshots)
    confirmed = [item for item in signals if item.status is ConfirmationStatus.CONFIRMED]
    oracle = ShadowEvaluationOracle(labels)
    first_snapshot: dict[UUID, IncomingReferralSnapshot] = {}
    for snapshot in snapshots:
        first_snapshot.setdefault(snapshot.case_id, snapshot)
    predicted = {item.case_id: item for item in confirmed}
    tp = fp = tn = fn = unresolved = 0
    false_causes: list[RootCause] = []
    missed: list[MissedPositive] = []
    for case_id, snapshot in first_snapshot.items():
        signal = predicted.get(case_id)
        as_of = signal.decided_at if signal else snapshot.available_at
        label = oracle.label_at(case_id, as_of)
        if label not in {ShadowLabelStatus.POSITIVE, ShadowLabelStatus.NEGATIVE}:
            unresolved += 1
        elif signal and label is ShadowLabelStatus.POSITIVE:
            tp += 1
        elif signal:
            fp += 1
            false_causes.append(
                RootCause(
                    case_id=case_id,
                    recommendation_id=signal.signal_id,
                    primary_category="misleading_structured_absence",
                    secondary_categories=("explicit_absence_not_operationally_required",),
                    source_references=signal.source_snapshot_ids,
                    mitigable_as_of_time=False,
                    introduces_latency=False,
                    may_reduce_recall=False,
                )
            )
        elif label is ShadowLabelStatus.POSITIVE:
            fn += 1
            initial_label = oracle.label_at(case_id, snapshot.available_at)
            disposition = (
                "resolved_during_confirmation_window"
                if initial_label is ShadowLabelStatus.POSITIVE
                else "strict_rule_exclusion"
            )
            missed.append(
                MissedPositive(
                    case_id=case_id,
                    exclusion_rule=disposition,
                    disposition="observe_only_analysis",
                    earlier_recommendation_possible=initial_label is ShadowLabelStatus.POSITIVE,
                    eventually_found_by_human=True,
                    fictional_operational_consequence="administrative review may occur later",
                    excessive_narrowing_warning=disposition == "strict_rule_exclusion",
                )
            )
        else:
            tn += 1
    latencies = [item.additional_latency_minutes for item in confirmed]
    detector = DetectorMetrics(
        detector_version=DetectorVersion.STRICT_V2,
        incoming_cases=len(first_snapshot),
        detector_positives=len(confirmed),
        abstentions=sum(item.status is ConfirmationStatus.INELIGIBLE for item in signals),
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        unresolved=unresolved,
        precision=_ratio(tp, tp + fp),
        recall=_ratio(tp, tp + fn),
        specificity=_ratio(tn, tn + fp),
        false_positive_rate=_ratio(fp, fp + tn),
        false_positive_review_hours=fp * 4 / 60,
        recommendation_latency_mean_minutes=mean(latencies) if latencies else None,
        recommendation_latency_p95_minutes=(
            sorted(latencies)[round((len(latencies) - 1) * 0.95)] if latencies else None
        ),
        audit_completeness=1.0,
        policy_compliance=1.0,
    )
    capacity_results = []
    all_events: list[QueueEvent] = []
    for capacity_config in CAPACITY_CONFIGS.values():
        events, metrics = apply_capacity(
            signals, capacity_config, incoming_case_count=len(first_snapshot)
        )
        capacity_results.append(metrics)
        all_events.extend(events)
    standard_surfaced = {
        item.case_id
        for item in all_events
        if item.capacity_profile.value == "standard" and item.status.value == "surfaced"
    }
    cohorts, chronology = _v2_guardrails(
        snapshots=snapshots,
        labels=labels,
        predicted=predicted,
        surfaced=standard_surfaced,
        minimum_sample=thresholds.minimum_cohort_sample,
    )
    precision = detector.precision
    recall = detector.recall
    standard_capacity = next(
        item for item in capacity_results if item.profile is CapacityProfile.STANDARD
    )
    fp_hours_100 = detector.false_positive_review_hours / max(1, detector.incoming_cases) * 100
    gates = {
        "precision": "pass"
        if precision is not None and precision >= thresholds.minimum_precision
        else "fail",
        "recall": "pass" if recall is not None and recall >= thresholds.minimum_recall else "fail",
        "false_positive_burden": "pass"
        if fp_hours_100 <= thresholds.maximum_false_positive_hours_per_100_cases
        else "fail",
        "recommendation_only": "pass",
        "capacity_is_not_detector_quality": "pass",
        "standard_capacity": "pass"
        if standard_capacity.deferred_recommendations == 0
        and standard_capacity.maximum_queue_depth
        <= CAPACITY_CONFIGS[CapacityProfile.STANDARD].maximum_active_queue_size
        else "fail",
    }
    breaches = tuple(key for key, value in gates.items() if value == "fail")
    sources = Counter(first_snapshot[item.case_id].source_system.value for item in confirmed)
    forms = Counter(first_snapshot[item.case_id].form_version for item in confirmed)
    rule = RulePerformance(
        reason_key="required_supporting_document_absent",
        detector_evaluations=len(first_snapshot),
        recommendations=len(confirmed),
        evaluable_recommendations=tp + fp,
        true_positives=tp,
        false_positives=fp,
        unresolved_labels=unresolved,
        precision=precision,
        recall_contribution=recall,
        false_positive_review_hours=detector.false_positive_review_hours,
        total_review_hours=len(confirmed) * 4 / 60,
        reviewer_agreement=precision,
        useful_and_correct_rate=precision,
        correct_but_redundant_rate=0,
        incorrect_rate=_ratio(fp, tp + fp),
        already_resolved_rate=0,
        retraction_rate=0,
        average_recommendation_latency_minutes=detector.recommendation_latency_mean_minutes,
        source_system_distribution=dict(sorted(sources.items())),
        form_version_distribution=dict(sorted(forms.items())),
        cohort_sample_size=len(confirmed),
        weekly_precision=(),
    )
    base = {
        "dataset": manifest.model_dump(mode="json"),
        "detector": detector.model_dump(mode="json"),
        "capacity": [item.model_dump(mode="json") for item in capacity_results],
        "false_causes": [item.model_dump(mode="json") for item in false_causes],
    }
    return DatasetEvaluation(
        dataset=manifest,
        detector=detector,
        capacity=tuple(capacity_results),
        rule_performance=(rule,),
        false_positive_causes=tuple(false_causes),
        redundancy_causes={
            "resolved_during_confirmation_window": sum(
                item.status is ConfirmationStatus.RESOLVED for item in signals
            )
        },
        missed_positives=tuple(missed),
        cohort_guardrails=cohorts,
        chronological_windows=chronology,
        queue_events=tuple(all_events),
        stop_condition_breaches=breaches,
        promotion_gates=gates,
        promotion_assessment="eligible_for_further_shadow_review"
        if not breaches
        else "do_not_promote",
        detector_fingerprint=config.detector_fingerprint,
        evaluation_fingerprint=locked_fingerprint(base),
    )
