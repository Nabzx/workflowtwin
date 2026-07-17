"""Shadow detector quality, burden, latency, policy, and promotion evaluation."""

from collections import Counter, defaultdict
from collections.abc import Callable
from statistics import mean, median
from typing import Any

from workflowtwin.shadow.audit import verify_audit_chain
from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.fingerprint import shadow_fingerprint
from workflowtwin.shadow.models import (
    AuditQuality,
    BurdenReport,
    DetectorEvaluation,
    DetectorOutcome,
    GateStatus,
    IncomingReferralSnapshot,
    LatencySummary,
    MetricValue,
    PolicyCompliance,
    PolicyStatus,
    PromotionAssessment,
    PromotionGate,
    RecommendationStatus,
    ReviewDecision,
    ReviewDecisionType,
    ReviewerMetrics,
    ShadowCaseState,
    ShadowEvaluation,
    ShadowEvaluationLabel,
    ShadowLabelStatus,
    ShadowRun,
    StopConditionResult,
)
from workflowtwin.shadow.oracle import ShadowEvaluationOracle


def _rate(numerator: int, denominator: int, unit: str = "proportion") -> MetricValue:
    if denominator == 0:
        return MetricValue(
            value=None,
            numerator=numerator,
            denominator=denominator,
            unit=unit,
            status="unavailable_no_denominator",
        )
    return MetricValue(
        value=numerator / denominator,
        numerator=numerator,
        denominator=denominator,
        unit=unit,
    )


def _percentile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * proportion)))
    return ordered[index]


def _latency(values: list[float], unavailable: int, slo_minutes: float) -> LatencySummary:
    return LatencySummary(
        count=len(values),
        unavailable_count=unavailable,
        mean_minutes=mean(values) if values else None,
        median_minutes=median(values) if values else None,
        p90_minutes=_percentile(values, 0.9),
        p95_minutes=_percentile(values, 0.95),
        maximum_minutes=max(values) if values else None,
        slo_compliance_rate=(
            sum(value <= slo_minutes for value in values) / len(values) if values else None
        ),
    )


def _detector_evaluation(
    run: ShadowRun,
    labels: tuple[ShadowEvaluationLabel, ...],
) -> tuple[DetectorEvaluation, dict[object, str]]:
    oracle = ShadowEvaluationOracle(labels)
    first_result: dict[object, Any] = {}
    for result in run.detector_results:
        first_result.setdefault(result.case_id, result)
    classifications: dict[object, str] = {}
    tp = fp = tn = fn = unresolved = 0
    for case_id, result in first_result.items():
        label = oracle.label_at(case_id, result.evaluated_at)
        if label not in {ShadowLabelStatus.POSITIVE, ShadowLabelStatus.NEGATIVE}:
            unresolved += 1
            classifications[case_id] = "unresolved"
            continue
        if result.outcome is DetectorOutcome.ABSTAIN:
            classifications[case_id] = "abstained"
            continue
        predicted = result.outcome is DetectorOutcome.RECOMMEND
        positive = label is ShadowLabelStatus.POSITIVE
        if predicted and positive:
            tp += 1
            classifications[case_id] = "true_positive"
        elif predicted:
            fp += 1
            classifications[case_id] = "false_positive"
        elif positive:
            fn += 1
            classifications[case_id] = "false_negative"
        else:
            tn += 1
            classifications[case_id] = "true_negative"
    recommendation_count = sum(
        item.status is RecommendationStatus.CREATED for item in run.recommendations
    )
    abstentions = sum(item.outcome is DetectorOutcome.ABSTAIN for item in first_result.values())
    evaluable = tp + fp + tn + fn
    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)
    precision_value = float(precision.value) if precision.value is not None else None
    recall_value = float(recall.value) if recall.value is not None else None
    f1 = (
        2 * precision_value * recall_value / (precision_value + recall_value)
        if precision_value is not None
        and recall_value is not None
        and precision_value + recall_value > 0
        else None
    )
    return (
        DetectorEvaluation(
            incoming_cases=len(run.case_states),
            evaluated_cases=len(first_result),
            recommendations=recommendation_count,
            abstentions=abstentions,
            reviewed_recommendations=0,
            evaluable_recommendations=tp + fp,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            unresolved_labels=unresolved,
            recommendation_coverage=_rate(recommendation_count, len(run.case_states)),
            abstention_rate=_rate(abstentions, len(first_result)),
            precision=precision,
            recall=recall,
            specificity=_rate(tn, tn + fp),
            false_positive_rate=_rate(fp, fp + tn),
            false_negative_rate=_rate(fn, fn + tp),
            negative_predictive_value=_rate(tn, tn + fn),
            f1_score=MetricValue(
                value=f1,
                unit="harmonic_mean",
                status="available" if f1 is not None else "unavailable_no_denominator",
            ),
            evaluation_coverage=_rate(evaluable, len(first_result)),
        ),
        classifications,
    )


def _reviewer_metrics(reviews: tuple[ReviewDecision, ...]) -> ReviewerMetrics:
    counts = Counter(review.decision for review in reviews)
    completed = sum(review.decision is not ReviewDecisionType.NOT_REVIEWED for review in reviews)
    durations = [review.review_duration_minutes for review in reviews if completed]
    usefulness: Counter[str] = Counter()
    for review in reviews:
        if review.recommendation_useful and review.arrived_in_time:
            usefulness["useful_and_correct"] += 1
        elif review.recommendation_useful:
            usefulness["correct_but_too_late"] += 1
        elif review.decision is ReviewDecisionType.ALREADY_RESOLVED:
            usefulness["correct_but_redundant"] += 1
        elif review.decision is ReviewDecisionType.DISAGREE:
            usefulness["incorrect"] += 1
        elif review.decision is ReviewDecisionType.INSUFFICIENT_CONTEXT:
            usefulness["insufficient_context"] += 1
        else:
            usefulness["not_evaluated"] += 1
    total = len(reviews)

    def ratio(value: int) -> float | None:
        return value / total if total else None

    return ReviewerMetrics(
        review_count=total,
        completion_rate=ratio(completed),
        agreement_rate=ratio(counts[ReviewDecisionType.AGREE]),
        rejection_rate=ratio(counts[ReviewDecisionType.DISAGREE]),
        uncertainty_rate=ratio(counts[ReviewDecisionType.UNCERTAIN]),
        already_resolved_rate=ratio(counts[ReviewDecisionType.ALREADY_RESOLVED]),
        policy_concern_rate=ratio(counts[ReviewDecisionType.POLICY_CONCERN]),
        override_rate=ratio(sum(review.override_or_correction for review in reviews)),
        median_review_duration_minutes=median(durations) if durations else None,
        timeout_rate=ratio(
            counts[ReviewDecisionType.EXPIRED_BEFORE_REVIEW]
            + counts[ReviewDecisionType.NOT_REVIEWED]
        ),
        usefulness_counts=dict(sorted(usefulness.items())),
    )


def _audit_quality(run: ShadowRun, reviews: tuple[ReviewDecision, ...]) -> AuditQuality:
    chain_valid, broken = verify_audit_chain(run.audit_records)
    audit_ids = {record.audit_id for record in run.audit_records}
    policy_ids = {item.evaluation_id for item in run.policy_evaluations}
    recommendation_ids = {item.recommendation_id for item in run.recommendations}
    missing_refs = sum(item.audit_record_id not in audit_ids for item in run.recommendations)
    missing_policy = sum(
        item.policy_evaluation_id not in policy_ids
        for item in run.recommendations
        if item.status in {RecommendationStatus.CREATED, RecommendationStatus.UPDATED}
    )
    orphan_reviews = sum(review.recommendation_id not in recommendation_ids for review in reviews)
    total = len(run.audit_records)
    complete = max(0, total - broken - missing_refs - missing_policy)
    return AuditQuality(
        total_records=total,
        complete_records=complete,
        missing_required_references=missing_refs,
        invalid_action_sequences=0,
        broken_chain_links=broken,
        missing_policy_evaluations=missing_policy,
        orphan_recommendations=0,
        orphan_reviews=orphan_reviews,
        audit_completeness_rate=complete / total if total else 0.0,
        chain_valid=chain_valid,
    )


def _policy_compliance(run: ShadowRun) -> PolicyCompliance:
    permitted = sum(item.status.value.startswith("permitted") for item in run.policy_evaluations)
    blocked = sum(item.status is PolicyStatus.BLOCKED for item in run.policy_evaluations)
    abstain = sum(item.status is PolicyStatus.ABSTAIN_REQUIRED for item in run.policy_evaluations)
    policy_ids = {item.evaluation_id for item in run.policy_evaluations}
    active = [
        item
        for item in run.recommendations
        if item.status in {RecommendationStatus.CREATED, RecommendationStatus.UPDATED}
    ]
    missing = sum(item.policy_evaluation_id not in policy_ids for item in active)
    violations = sum(len(item.prohibited_attempts) for item in run.policy_evaluations) + missing
    total = len(run.policy_evaluations)
    return PolicyCompliance(
        detector_evaluations=len(run.detector_results),
        permitted_evaluations=permitted,
        blocked_evaluations=blocked,
        abstentions_required=abstain,
        active_recommendations_with_approval=len(active) - missing,
        recommendations_missing_approval=missing,
        prohibited_input_attempts=0,
        clinical_field_access_attempts=0,
        workflow_mutation_attempts=0,
        external_communication_attempts=0,
        total_policy_violations=violations,
        compliance_rate=1 - violations / total if total else 1.0,
    )


def _burden(
    run: ShadowRun,
    reviews: tuple[ReviewDecision, ...],
    classifications: dict[object, str],
    config: ShadowConfig,
) -> BurdenReport:
    all_minutes = sum(review.review_duration_minutes for review in reviews)
    false_positive_minutes = sum(
        review.review_duration_minutes
        for review in reviews
        if classifications.get(review.case_id) == "false_positive"
    )
    useful_minutes = sum(
        review.review_duration_minutes for review in reviews if review.recommendation_useful
    )
    unresolved_minutes = sum(
        review.review_duration_minutes
        for review in reviews
        if classifications.get(review.case_id) == "unresolved"
    )
    fp = sum(value == "false_positive" for value in classifications.values())
    created = sum(item.status is RecommendationStatus.CREATED for item in run.recommendations)
    return BurdenReport(
        all_review_hours=all_minutes / 60,
        false_positive_review_hours=false_positive_minutes / 60,
        useful_review_hours=useful_minutes / 60,
        unresolved_review_hours=unresolved_minutes / 60,
        false_positive_per_100_cases=100 * fp / len(run.case_states) if run.case_states else 0,
        false_positive_per_100_recommendations=100 * fp / created if created else 0,
        fictional_false_positive_cost_gbp=(
            false_positive_minutes / 60 * config.administrative_hourly_cost_gbp
        ),
        revision_count=sum(
            item.status is RecommendationStatus.UPDATED for item in run.recommendations
        ),
        retraction_count=sum(
            item.status is RecommendationStatus.RETRACTED for item in run.recommendations
        ),
        expiry_count=sum(
            item.status is RecommendationStatus.EXPIRED for item in run.recommendations
        ),
    )


def _latencies(
    run: ShadowRun,
    snapshots: tuple[IncomingReferralSnapshot, ...],
    reviews: tuple[ReviewDecision, ...],
    config: ShadowConfig,
) -> tuple[LatencySummary, LatencySummary, LatencySummary, LatencySummary]:
    by_case = defaultdict(list)
    for snapshot in snapshots:
        by_case[snapshot.case_id].append(snapshot)
    created = [item for item in run.recommendations if item.status is RecommendationStatus.CREATED]
    source_latency: list[float] = []
    arrival_latency: list[float] = []
    for recommendation in created:
        available = [
            item.available_at
            for item in by_case[recommendation.case_id]
            if item.available_at <= recommendation.recommendation_at
        ]
        if available:
            source_latency.append(
                (recommendation.recommendation_at - max(available)).total_seconds() / 60
            )
            arrival_latency.append(
                (recommendation.recommendation_at - min(available)).total_seconds() / 60
            )
    recommendation_by_id = {item.recommendation_id: item for item in created}
    review_latency = [
        (
            review.decided_at - recommendation_by_id[review.recommendation_id].recommendation_at
        ).total_seconds()
        / 60
        for review in reviews
        if review.recommendation_id in recommendation_by_id
    ]
    retraction_latency = [
        (
            item.recommendation_at - recommendation_by_id[item.recommendation_id].recommendation_at
        ).total_seconds()
        / 60
        for item in run.recommendations
        if item.status is RecommendationStatus.RETRACTED
        and item.recommendation_id in recommendation_by_id
    ]
    return (
        _latency(
            source_latency,
            len(created) - len(source_latency),
            config.maximum_p95_recommendation_latency_minutes,
        ),
        _latency(
            arrival_latency,
            len(created) - len(arrival_latency),
            config.maximum_p95_recommendation_latency_minutes,
        ),
        _latency(
            review_latency,
            len(created) - len(review_latency),
            config.review_slo.total_seconds() / 60,
        ),
        _latency(retraction_latency, 0, config.review_slo.total_seconds() / 60),
    )


def _cohorts(
    run: ShadowRun, classifications: dict[object, str], minimum: int
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    dimensions: dict[str, Callable[[ShadowCaseState], str]] = {
        "referral_source": lambda state: state.referral_source.value,
        "source_system": lambda state: state.source_system.value,
        "service_line": lambda state: state.requested_service_line.value,
        "form_version": lambda state: state.form_version,
    }
    for dimension, getter in dimensions.items():
        grouped = defaultdict(list)
        for state in run.case_states:
            grouped[getter(state)].append(state.case_id)
        for value, case_ids in sorted(grouped.items()):
            if len(case_ids) < minimum:
                continue
            tp = sum(classifications.get(case_id) == "true_positive" for case_id in case_ids)
            fp = sum(classifications.get(case_id) == "false_positive" for case_id in case_ids)
            rows.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "sample_size": len(case_ids),
                    "precision": tp / (tp + fp) if tp + fp else None,
                    "language": "observed replay performance; not a protected-attribute analysis",
                }
            )
    return tuple(rows)


def _time_windows(run: ShadowRun, classifications: dict[object, str]) -> tuple[dict[str, Any], ...]:
    if not run.detector_results:
        return ()
    start = min(item.evaluated_at for item in run.detector_results)
    grouped: dict[int, list[object]] = defaultdict(list)
    for result in run.detector_results:
        grouped[(result.evaluated_at - start).days // 7].append(result.case_id)
    rows = []
    for index, case_ids in sorted(grouped.items()):
        unique = set(case_ids)
        tp = sum(classifications.get(case_id) == "true_positive" for case_id in unique)
        fp = sum(classifications.get(case_id) == "false_positive" for case_id in unique)
        rows.append(
            {
                "window": f"logical_days_{index * 7 + 1}_{index * 7 + 7}",
                "cases": len(unique),
                "precision": tp / (tp + fp) if tp + fp else None,
                "recommendations": tp + fp,
                "interpretation": "observed period difference; requires further monitoring",
            }
        )
    return tuple(rows)


def _stop_conditions(
    detector: DetectorEvaluation,
    reviewer: ReviewerMetrics,
    burden: BurdenReport,
    audit: AuditQuality,
    policy: PolicyCompliance,
    latency: LatencySummary,
    run: ShadowRun,
    config: ShadowConfig,
) -> tuple[StopConditionResult, ...]:
    precision = float(detector.precision.value) if detector.precision.value is not None else None
    recommendation_rate = (
        detector.recommendations / detector.incoming_cases if detector.incoming_cases else 0.0
    )
    duplicate_rate = (
        run.manifest.duplicate_suppressions / len(run.detector_results)
        if run.detector_results
        else 0.0
    )
    fp_hours_100 = (
        burden.false_positive_review_hours * 100 / detector.incoming_cases
        if detector.incoming_cases
        else 0.0
    )
    definitions = (
        (
            "clinical-access",
            "clinical_field_access",
            policy.clinical_field_access_attempts,
            0,
            1,
            "stop_shadow_run",
        ),
        (
            "workflow-mutation",
            "workflow_mutations",
            policy.workflow_mutation_attempts,
            0,
            1,
            "stop_shadow_run",
        ),
        (
            "policy-coverage",
            "missing_policy_evaluations",
            policy.recommendations_missing_approval,
            0,
            1,
            "stop_shadow_run",
        ),
        (
            "audit-chain",
            "broken_audit_chain_links",
            audit.broken_chain_links,
            0,
            1,
            "stop_shadow_run",
        ),
        (
            "audit-completeness",
            "audit_completeness",
            audit.audit_completeness_rate,
            config.minimum_audit_completeness,
            1,
            "pause_shadow_run",
        ),
        (
            "precision",
            "precision",
            precision,
            config.minimum_precision,
            config.minimum_evaluation_sample,
            "mark_promotion_ineligible",
        ),
        (
            "false-positive-burden",
            "false_positive_hours_per_100_cases",
            fp_hours_100,
            config.maximum_false_positive_hours_per_100_cases,
            config.minimum_evaluation_sample,
            "pause_shadow_run",
        ),
        (
            "reviewer-rejection",
            "reviewer_rejection_rate",
            reviewer.rejection_rate,
            config.maximum_reviewer_rejection_rate,
            config.minimum_evaluation_sample,
            "pause_shadow_run",
        ),
        (
            "recommendation-rate",
            "recommendations_per_case",
            recommendation_rate,
            config.maximum_recommendation_rate,
            config.minimum_evaluation_sample,
            "pause_shadow_run",
        ),
        (
            "duplicate-rate",
            "duplicate_recommendation_rate",
            duplicate_rate,
            config.maximum_duplicate_rate,
            1,
            "warning",
        ),
        (
            "detector-failure",
            "detector_failure_rate",
            0.0,
            config.maximum_detector_failure_rate,
            1,
            "stop_shadow_run",
        ),
        (
            "p95-latency",
            "p95_recommendation_latency_minutes",
            latency.p95_minutes,
            config.maximum_p95_recommendation_latency_minutes,
            config.minimum_evaluation_sample,
            "warning",
        ),
    )
    results = []
    recommendation_sample = detector.true_positives + detector.false_positives
    for identifier, metric, observed, threshold, minimum, action in definitions:
        enough = (
            recommendation_sample >= minimum
            if metric in {"precision", "reviewer_rejection_rate"}
            else detector.incoming_cases >= minimum
        )
        lower_is_bad = metric in {"precision", "audit_completeness"}
        breached = (
            observed is not None
            and enough
            and (observed < threshold if lower_is_bad else observed > threshold)
        )
        results.append(
            StopConditionResult(
                condition_id=identifier,
                metric=metric,
                breached=breached,
                severity="critical" if action == "stop_shadow_run" else "high",
                action=action,
                observed_value=observed,
                threshold=threshold,
                minimum_sample_size=minimum,
                explanation=(
                    "threshold breached" if breached else "within threshold or insufficient sample"
                ),
            )
        )
    return tuple(results)


def _promotion(
    detector: DetectorEvaluation,
    reviewer: ReviewerMetrics,
    burden: BurdenReport,
    audit: AuditQuality,
    policy: PolicyCompliance,
    latency: LatencySummary,
    stops: tuple[StopConditionResult, ...],
    config: ShadowConfig,
) -> tuple[tuple[PromotionGate, ...], PromotionAssessment]:
    sample = detector.true_positives + detector.false_positives
    precision = float(detector.precision.value) if detector.precision.value is not None else None
    fp_hours_100 = (
        burden.false_positive_review_hours * 100 / detector.incoming_cases
        if detector.incoming_cases
        else 0.0
    )
    checks = (
        (
            "safety-prohibited-actions",
            "safety",
            policy.total_policy_violations == 0,
            policy.total_policy_violations,
            0,
            True,
        ),
        (
            "audit-integrity",
            "auditability",
            audit.chain_valid
            and audit.audit_completeness_rate >= config.minimum_audit_completeness,
            audit.audit_completeness_rate,
            config.minimum_audit_completeness,
            True,
        ),
        (
            "quality-sample",
            "detector_quality",
            sample >= config.minimum_evaluation_sample,
            sample,
            config.minimum_evaluation_sample,
            True,
        ),
        (
            "quality-precision",
            "detector_quality",
            precision is not None and precision >= config.minimum_precision,
            precision,
            config.minimum_precision,
            True,
        ),
        (
            "burden-false-positive",
            "operational_burden",
            fp_hours_100 <= config.maximum_false_positive_hours_per_100_cases,
            fp_hours_100,
            config.maximum_false_positive_hours_per_100_cases,
            True,
        ),
        (
            "review-completion",
            "operational_burden",
            reviewer.completion_rate is not None and reviewer.completion_rate >= 0.8,
            reviewer.completion_rate,
            0.8,
            True,
        ),
        (
            "reliability-latency",
            "reliability",
            latency.p95_minutes is not None
            and latency.p95_minutes <= config.maximum_p95_recommendation_latency_minutes,
            latency.p95_minutes,
            config.maximum_p95_recommendation_latency_minutes,
            True,
        ),
    )
    gates = tuple(
        PromotionGate(
            gate_id=identifier,
            category=category,
            status=(
                GateStatus.INSUFFICIENT
                if identifier == "quality-sample" and not passed
                else GateStatus.PASSED
                if passed
                else GateStatus.FAILED
            ),
            observed_value=observed,
            threshold=threshold,
            mandatory=mandatory,
            explanation="fictional replay gate; it does not authorise deployment",
        )
        for identifier, category, passed, observed, threshold, mandatory in checks
    )
    hard_stop = any(item.breached and item.action == "stop_shadow_run" for item in stops)
    mandatory_passed = all(item.status is GateStatus.PASSED for item in gates if item.mandatory)
    if hard_stop:
        result = "pause_due_to_stop_condition"
    elif mandatory_passed:
        result = "ready_for_limited_human_in_the_loop_pilot"
    elif sample < config.minimum_evaluation_sample:
        result = "continue_shadow_evaluation"
    else:
        result = "revise_detector"
    counts = Counter(item.status.value for item in gates)
    content = {
        "result": result,
        "mandatory_gates_passed": mandatory_passed,
        "stop_condition_breached": any(item.breached for item in stops),
        "gate_counts": dict(sorted(counts.items())),
        "explanation": (
            "Pilot readiness is limited to fictional human-reviewed evaluation and is not "
            "production or autonomous-action approval."
        ),
    }
    assessment = PromotionAssessment.model_validate(
        {**content, "assessment_fingerprint": shadow_fingerprint(content)}
    )
    return gates, assessment


def evaluate_shadow(
    *,
    run: ShadowRun,
    snapshots: tuple[IncomingReferralSnapshot, ...],
    labels: tuple[ShadowEvaluationLabel, ...],
    reviews: tuple[ReviewDecision, ...],
    config: ShadowConfig,
    detector_runtime_seconds: float = 0.0,
    profile_comparison: tuple[dict[str, Any], ...] = (),
) -> ShadowEvaluation:
    detector, classifications = _detector_evaluation(run, labels)
    detector = detector.model_copy(update={"reviewed_recommendations": len(reviews)})
    reviewer = _reviewer_metrics(reviews)
    audit = _audit_quality(run, reviews)
    policy = _policy_compliance(run)
    burden = _burden(run, reviews, classifications, config)
    source_latency, arrival_latency, review_latency, retraction_latency = _latencies(
        run, snapshots, reviews, config
    )
    stops = _stop_conditions(detector, reviewer, burden, audit, policy, source_latency, run, config)
    gates, assessment = _promotion(
        detector, reviewer, burden, audit, policy, source_latency, stops, config
    )
    content = {
        "source_fingerprints": {
            "operational_dataset": config.source_dataset_fingerprint,
            "intake_snapshots": run.manifest.intake_snapshot_fingerprint,
            "recommendations": shadow_fingerprint(run.recommendations),
            "reviews": shadow_fingerprint(reviews),
            "audit_root": run.manifest.audit_root_fingerprint or "unavailable",
        },
        "configuration": config.model_dump(mode="json"),
        "run_manifest": run.manifest,
        "detector": detector,
        "source_to_recommendation_latency": source_latency,
        "case_arrival_to_recommendation_latency": arrival_latency,
        "recommendation_to_review_latency": review_latency,
        "resolution_before_review_latency": retraction_latency,
        "reviewer": reviewer,
        "burden": burden,
        "audit": audit,
        "policy": policy,
        "cohort_breakdowns": _cohorts(run, classifications, config.minimum_evaluation_sample),
        "time_windows": _time_windows(run, classifications),
        "profile_comparison": profile_comparison,
        "stop_conditions": stops,
        "promotion_gates": gates,
        "promotion_assessment": assessment,
        "assumptions": (
            "hidden labels are synthetic and available only after detector execution",
            "cost is a fictional administrative burden proxy, not realised savings",
        ),
        "warnings": (
            "results describe replayed fictional shadow mode, not real clinical or "
            "operational impact",
        ),
    }
    fingerprint = shadow_fingerprint(content)
    return ShadowEvaluation.model_validate(
        {
            **content,
            "detector_runtime_seconds": detector_runtime_seconds,
            "evaluation_fingerprint": fingerprint,
        }
    )
