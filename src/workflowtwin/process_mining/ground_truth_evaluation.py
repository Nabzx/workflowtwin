"""Separate post-discovery checks against synthetic bottleneck annotations."""

from dataclasses import dataclass

from workflowtwin.process_mining.models import (
    ProcessBottleneckCandidate,
    ProcessBottleneckEvaluation,
    ProcessGroundTruthEvaluation,
)
from workflowtwin.synthetic.models import BottleneckLabel, GenerationGroundTruth


@dataclass(frozen=True, slots=True)
class ExpectedProcessEvidence:
    label: BottleneckLabel
    candidate_type: str
    dimension: str
    value: str


EXPECTED = (
    ExpectedProcessEvidence(
        BottleneckLabel.INCOMPLETE_REFERRALS,
        "referral_source_rework_path",
        "referral_source",
        "gp_practice",
    ),
    ExpectedProcessEvidence(
        BottleneckLabel.ASSIGNMENT_CONGESTION,
        "service_line_assignment_delay",
        "service_line",
        "neurology",
    ),
    ExpectedProcessEvidence(
        BottleneckLabel.SCHEDULING_FRICTION,
        "service_line_scheduling_retries",
        "service_line",
        "respiratory",
    ),
    ExpectedProcessEvidence(
        BottleneckLabel.HANDOFF_COST,
        "service_line_reassignment",
        "service_line",
        "dermatology",
    ),
)


def evaluate_process_ground_truth(
    candidates: tuple[ProcessBottleneckCandidate, ...],
    ground_truth: GenerationGroundTruth | None,
    generation_run_id: str | None,
) -> ProcessGroundTruthEvaluation:
    if ground_truth is None:
        return ProcessGroundTruthEvaluation(
            status="not_evaluated",
            bottlenecks=(),
            detected_count=0,
            planted_count=0,
            false_negatives=(),
            unexpected_candidate_ids=(),
            notes=("no separate synthetic ground truth was supplied",),
        )
    if generation_run_id is None or ground_truth.run_id != generation_run_id:
        raise ValueError("ground truth generation run does not match process input")
    planted = {label for case in ground_truth.cases for label in case.bottlenecks}
    evaluations = []
    matched: set[str] = set()
    for expected in EXPECTED:
        if expected.label not in planted:
            continue
        matches = tuple(
            candidate
            for candidate in candidates
            if candidate.candidate_type == expected.candidate_type
            and candidate.cohort_dimension == expected.dimension
            and candidate.cohort_value == expected.value
        )
        matched.update(candidate.candidate_id for candidate in matches)
        evaluations.append(
            ProcessBottleneckEvaluation(
                bottleneck=expected.label.value,
                detected=bool(matches),
                evidence_ids=tuple(candidate.candidate_id for candidate in matches),
                expected_direction="elevated",
                observed_direction="elevated" if matches else None,
                sample_size=max((candidate.case_count for candidate in matches), default=0),
                materiality_met=bool(matches),
            )
        )
    return ProcessGroundTruthEvaluation(
        status="evaluated",
        bottlenecks=tuple(evaluations),
        detected_count=sum(result.detected for result in evaluations),
        planted_count=len(evaluations),
        false_negatives=tuple(result.bottleneck for result in evaluations if not result.detected),
        unexpected_candidate_ids=tuple(
            candidate.candidate_id
            for candidate in candidates
            if candidate.candidate_id not in matched
        ),
        notes=(
            "this is deterministic benchmark verification, not predictive-model accuracy",
            "unexpected candidates may reflect overlapping effects or synthetic variation",
        ),
    )
