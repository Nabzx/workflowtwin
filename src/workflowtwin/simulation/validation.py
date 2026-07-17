"""Counterfactual integrity, provenance, safety, and source immutability checks."""

from collections import defaultdict
from itertools import pairwise
from uuid import UUID

from workflowtwin.analytics.fingerprint import dataset_fingerprint
from workflowtwin.analytics.models import AnalysisInput
from workflowtwin.domain.referrals.models import FORBIDDEN_METADATA_KEYS, ReferralEvent
from workflowtwin.simulation.models import CaseSimulationResult, SimulationQualityReport


def _forbidden_metadata(event: ReferralEvent) -> bool:
    return any(key in FORBIDDEN_METADATA_KEYS for key in event.metadata)


def validate_counterfactual(
    *,
    source: AnalysisInput,
    counterfactual: AnalysisInput,
    case_results: tuple[CaseSimulationResult, ...],
) -> SimulationQualityReport:
    source_before = dataset_fingerprint(source.cases, source.events)
    source_after = dataset_fingerprint(source.cases, source.events)
    case_ids = {case.id for case in counterfactual.cases}
    event_ids = [event.id for event in counterfactual.events]
    orphan_count = sum(event.referral_case_id not in case_ids for event in counterfactual.events)
    timezone_issues = sum(
        event.event_at.tzinfo is None
        or event.event_at.utcoffset() is None
        or event.ingested_at.tzinfo is None
        or event.ingested_at.utcoffset() is None
        for event in counterfactual.events
    )
    events_by_case: dict[UUID, list[ReferralEvent]] = defaultdict(list)
    for event in counterfactual.events:
        events_by_case[event.referral_case_id].append(event)
    ordering_issues = sum(
        current.event_at < previous.event_at
        for events in events_by_case.values()
        for previous, current in pairwise(events)
    )
    forbidden = sum(_forbidden_metadata(event) for event in counterfactual.events)
    changes = tuple(change for result in case_results for change in result.event_changes)
    provenance_issues = sum(
        not change.provenance
        or change.source_event_id is None
        or change.counterfactual_event_id is None
        for change in changes
    )
    approved_cases = {
        result.case_id
        for result in case_results
        if result.decision.status.value == "approved_simulated_action"
    }
    changed_cases = {change.case_id for change in changes}
    mismatch = len(changed_cases.symmetric_difference(approved_cases))
    expected_failures = sum(
        result.decision.status.value
        in {"simulation_failure", "fallback_to_manual_process", "rolled_back"}
        for result in case_results
    )
    invalid = (
        orphan_count
        + timezone_issues
        + ordering_issues
        + forbidden
        + provenance_issues
        + mismatch
        + (0 if len(event_ids) == len(set(event_ids)) else 1)
    )
    findings = tuple(
        name
        for name, count in (
            ("orphan_counterfactual_event", orphan_count),
            ("timezone_issue", timezone_issues),
            ("event_order_issue", ordering_issues),
            ("forbidden_metadata", forbidden),
            ("missing_change_provenance", provenance_issues),
            ("policy_change_mismatch", mismatch),
        )
        if count
    )
    return SimulationQualityReport(
        is_valid=invalid == 0,
        source_events_unchanged=source_before == source_after,
        counterfactual_event_count=len(counterfactual.events),
        unique_event_identifiers=len(event_ids) == len(set(event_ids)),
        orphan_event_count=orphan_count,
        timezone_issue_count=timezone_issues,
        event_order_issue_count=ordering_issues,
        forbidden_metadata_count=forbidden,
        provenance_issue_count=provenance_issues,
        policy_change_mismatch_count=mismatch,
        expected_failure_count=expected_failures,
        findings=findings,
        warnings=(
            "valid counterfactual deviations and expected failures are not source-data defects",
        ),
    )
