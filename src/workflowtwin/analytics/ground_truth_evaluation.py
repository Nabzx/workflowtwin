"""Post-analysis benchmark checks against separate synthetic ground truth."""

from dataclasses import dataclass

from workflowtwin.analytics.models import (
    BaselineFinding,
    BottleneckEvaluation,
    EvaluationStatus,
    GroundTruthEvaluation,
)
from workflowtwin.synthetic.models import BottleneckLabel, GenerationGroundTruth


@dataclass(frozen=True, slots=True)
class ExpectedDetection:
    label: BottleneckLabel
    cohort_dimension: str
    cohort_value: str
    finding_types: tuple[str, ...]
    expected_direction: str


EXPECTED_DETECTIONS = (
    ExpectedDetection(
        BottleneckLabel.INCOMPLETE_REFERRALS,
        "referral_source",
        "gp_practice",
        ("lower_first_pass_completeness",),
        "lower",
    ),
    ExpectedDetection(
        BottleneckLabel.ASSIGNMENT_CONGESTION,
        "service_line",
        "neurology",
        ("longer_assignment_wait", "longer_booking_time"),
        "higher",
    ),
    ExpectedDetection(
        BottleneckLabel.SCHEDULING_FRICTION,
        "service_line",
        "respiratory",
        ("elevated_failed_scheduling", "longer_booking_time"),
        "higher",
    ),
    ExpectedDetection(
        BottleneckLabel.HANDOFF_COST,
        "service_line",
        "dermatology",
        ("elevated_reassignment", "elevated_handoffs"),
        "higher",
    ),
)


def not_evaluated() -> GroundTruthEvaluation:
    return GroundTruthEvaluation(
        status=EvaluationStatus.NOT_EVALUATED,
        bottlenecks=(),
        detected_count=0,
        planted_count=0,
        false_negatives=(),
        unexpected_finding_ids=(),
        notes=("no synthetic ground truth was supplied",),
    )


def evaluate_findings(
    findings: tuple[BaselineFinding, ...],
    ground_truth: GenerationGroundTruth | None,
    generation_run_id: str | None,
) -> GroundTruthEvaluation:
    """Evaluate planted patterns after, and independently from, detection."""
    if ground_truth is None:
        return not_evaluated()
    if generation_run_id is None or ground_truth.run_id != generation_run_id:
        raise ValueError("ground truth generation run does not match the analysis input")
    planted = {bottleneck for case in ground_truth.cases for bottleneck in case.bottlenecks}
    evaluations = []
    matched_ids = set()
    for expected in EXPECTED_DETECTIONS:
        if expected.label not in planted:
            continue
        match = next(
            (
                finding
                for finding in findings
                if finding.cohort_dimension == expected.cohort_dimension
                and finding.cohort_value == expected.cohort_value
                and finding.finding_type in expected.finding_types
            ),
            None,
        )
        if match is not None:
            matched_ids.add(match.finding_id)
        evaluations.append(
            BottleneckEvaluation(
                bottleneck=expected.label.value,
                detected=match is not None,
                finding_id=match.finding_id if match else None,
                expected_cohort=f"{expected.cohort_dimension}={expected.cohort_value}",
                expected_direction=expected.expected_direction,
                observed_direction=expected.expected_direction if match else None,
                materiality_met=match is not None,
            )
        )
    false_negatives = tuple(
        evaluation.bottleneck for evaluation in evaluations if not evaluation.detected
    )
    return GroundTruthEvaluation(
        status=EvaluationStatus.EVALUATED,
        bottlenecks=tuple(evaluations),
        detected_count=sum(evaluation.detected for evaluation in evaluations),
        planted_count=len(evaluations),
        false_negatives=false_negatives,
        unexpected_finding_ids=tuple(
            finding.finding_id for finding in findings if finding.finding_id not in matched_ids
        ),
        notes=(
            "benchmark verification is not predictive-model accuracy",
            "unexpected findings can reflect overlapping effects or seeded natural variation",
        ),
    )
