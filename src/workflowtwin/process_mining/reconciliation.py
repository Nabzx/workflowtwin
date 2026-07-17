"""Link process evidence to existing baseline findings without recalculation."""

from workflowtwin.analytics.models import BaselineAnalysis
from workflowtwin.process_mining.models import (
    BaselineReconciliation,
    ProcessBottleneckCandidate,
)

EXPECTED_CANDIDATE_TYPES = {
    "lower_first_pass_completeness": {"referral_source_rework_path"},
    "elevated_rework": {"referral_source_rework_path", "service_line_scheduling_retries"},
    "longer_assignment_wait": {"service_line_assignment_delay"},
    "longer_booking_time": {
        "service_line_assignment_delay",
        "service_line_scheduling_retries",
    },
    "elevated_failed_scheduling": {"service_line_scheduling_retries"},
    "elevated_reassignment": {"service_line_reassignment"},
    "elevated_handoffs": {"service_line_reassignment"},
}


def reconcile_baseline(
    baseline: BaselineAnalysis | None,
    candidates: tuple[ProcessBottleneckCandidate, ...],
) -> tuple[BaselineReconciliation, ...]:
    if baseline is None:
        return ()
    results = []
    for finding in baseline.findings:
        expected = EXPECTED_CANDIDATE_TYPES.get(finding.finding_type, set())
        matches = tuple(
            candidate
            for candidate in candidates
            if candidate.candidate_type in expected
            and candidate.cohort_dimension == finding.cohort_dimension
            and candidate.cohort_value == finding.cohort_value
        )
        sample_size = max((candidate.case_count for candidate in matches), default=0)
        results.append(
            BaselineReconciliation(
                baseline_finding_id=finding.finding_id,
                supporting_process_ids=tuple(candidate.candidate_id for candidate in matches),
                supports_finding=bool(matches),
                contradicts_finding=False,
                evidence=(
                    "process transitions or variants support the baseline cohort pattern"
                    if matches
                    else "no configured process candidate independently met materiality"
                ),
                sample_size=sample_size,
                caveats=(
                    "absence of a process candidate does not disprove the baseline metric",
                    "both analyses are descriptive and do not establish causality",
                ),
            )
        )
    return tuple(results)
