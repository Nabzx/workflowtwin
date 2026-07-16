"""Dataset integrity and expected-defect validation."""

from collections import Counter, defaultdict
from itertools import pairwise
from typing import Any
from uuid import UUID

from workflowtwin.domain.referrals.enums import TERMINAL_STATUSES, EventType
from workflowtwin.domain.referrals.models import FORBIDDEN_METADATA_KEYS
from workflowtwin.synthetic.manifest import dataset_fingerprint
from workflowtwin.synthetic.models import (
    DatasetValidationReport,
    DefectType,
    GeneratedDataset,
    ValidationFinding,
    ValidationSeverity,
)

TERMINAL_EVENTS = {
    EventType.REFERRAL_COMPLETED,
    EventType.REFERRAL_CANCELLED,
    EventType.REFERRAL_REJECTED,
    EventType.REFERRAL_CLOSED_OTHER,
}


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalised = str(key).strip().lower().replace("-", "_").replace(" ", "_")
            if normalised in FORBIDDEN_METADATA_KEYS or _contains_forbidden_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def validate_dataset(dataset: GeneratedDataset) -> DatasetValidationReport:
    """Report invalid records separately from known valid synthetic oddities."""
    case_ids = [case.id for case in dataset.cases]
    known_case_ids = set(case_ids)
    event_ids = [event.id for event in dataset.events]
    event_identity = [(event.source_system, event.external_event_id) for event in dataset.events]
    events_by_case: dict[UUID, list[Any]] = defaultdict(list)
    for event in dataset.events:
        events_by_case[event.referral_case_id].append(event)

    orphan_count = sum(event.referral_case_id not in known_case_ids for event in dataset.events)
    duplicate_event_ids = len(event_ids) - len(set(event_ids))
    duplicate_external = len(event_identity) - len(set(event_identity))
    invalid_terminal = 0
    for case in dataset.cases:
        terminal_events = [
            event for event in events_by_case[case.id] if event.event_type in TERMINAL_EVENTS
        ]
        if case.status in TERMINAL_STATUSES:
            if case.closed_at is None or len(terminal_events) != 1:
                invalid_terminal += 1
        elif case.closed_at is not None or terminal_events:
            invalid_terminal += 1

    cases_without_events = sum(case.id not in events_by_case for case in dataset.cases)
    event_time_regressions = 0
    out_of_order_ingestion = 0
    for case_id in known_case_ids:
        case_events = events_by_case[case_id]
        event_time_regressions += sum(
            current.event_at < previous.event_at for previous, current in pairwise(case_events)
        )
        event_order = sorted(case_events, key=lambda event: (event.event_at, event.id.hex))
        if any(
            current.ingested_at < previous.ingested_at
            for previous, current in pairwise(event_order)
        ):
            out_of_order_ingestion += 1

    timezone_issues = sum(
        timestamp.tzinfo is None or timestamp.utcoffset() is None
        for case in dataset.cases
        for timestamp in (case.received_at, case.created_at, case.updated_at)
    ) + sum(
        timestamp.tzinfo is None or timestamp.utcoffset() is None
        for event in dataset.events
        for timestamp in (event.event_at, event.ingested_at)
    )
    schema_mismatches = sum(case.schema_version != 1 for case in dataset.cases) + sum(
        event.schema_version != 1 for event in dataset.events
    )
    forbidden_metadata = sum(_contains_forbidden_key(event.metadata) for event in dataset.events)
    event_type_counts = Counter(event.event_type.value for event in dataset.events)
    outcome_counts = Counter(
        case.status.value for case in dataset.cases if case.status in TERMINAL_STATUSES
    )
    stuck_count = sum(
        annotation.is_intentionally_stuck for annotation in dataset.ground_truth.cases
    )
    delayed_count = sum(
        DefectType.DELAYED_INGESTION in annotation.defects
        for annotation in dataset.ground_truth.cases
    )
    actual_fingerprint = dataset_fingerprint(dataset.cases, dataset.events)
    manifest_mismatch = int(
        dataset.manifest.generated_case_count != len(dataset.cases)
        or dataset.manifest.generated_event_count != len(dataset.events)
        or dataset.manifest.dataset_fingerprint != actual_fingerprint
    )

    invalid_counts = {
        "orphan_events": orphan_count,
        "duplicate_event_ids": duplicate_event_ids,
        "duplicate_external_events": duplicate_external,
        "invalid_terminal_cases": invalid_terminal,
        "cases_without_events": cases_without_events,
        "event_time_regressions": event_time_regressions,
        "timezone_issues": timezone_issues,
        "schema_version_mismatches": schema_mismatches,
        "forbidden_metadata": forbidden_metadata,
        "manifest_mismatch": manifest_mismatch,
    }
    findings = [
        ValidationFinding(
            severity=ValidationSeverity.INVALID,
            code=code,
            count=count,
            message=f"Dataset contains {count} invalid occurrence(s) of {code}.",
        )
        for code, count in invalid_counts.items()
        if count
    ]
    duplicate_attempt_count = len(dataset.ground_truth.duplicate_attempts)
    if duplicate_attempt_count:
        findings.append(
            ValidationFinding(
                severity=ValidationSeverity.EXPECTED_DEFECT,
                code="duplicate_source_attempts",
                count=duplicate_attempt_count,
                message="Duplicate attempts are labelled outside canonical operational events.",
            )
        )
    if delayed_count:
        findings.append(
            ValidationFinding(
                severity=ValidationSeverity.EXPECTED_DEFECT,
                code="delayed_ingestion",
                count=delayed_count,
                message="Delayed ingestion is valid and intentionally generated.",
            )
        )
    if out_of_order_ingestion:
        findings.append(
            ValidationFinding(
                severity=ValidationSeverity.EXPECTED_DEFECT,
                code="out_of_order_ingestion",
                count=out_of_order_ingestion,
                message="Ingestion order differs from event-time order for labelled cases.",
            )
        )

    return DatasetValidationReport(
        is_valid=not any(invalid_counts.values()),
        case_count=len(dataset.cases),
        event_count=len(dataset.events),
        orphan_event_count=orphan_count,
        duplicate_event_id_count=duplicate_event_ids,
        duplicate_external_event_count=duplicate_external,
        invalid_terminal_case_count=invalid_terminal,
        cases_without_events=cases_without_events,
        event_time_regression_count=event_time_regressions,
        timezone_issue_count=timezone_issues,
        schema_version_mismatch_count=schema_mismatches,
        forbidden_metadata_count=forbidden_metadata,
        event_type_counts=dict(sorted(event_type_counts.items())),
        terminal_outcome_counts=dict(sorted(outcome_counts.items())),
        stuck_case_count=stuck_count,
        delayed_ingestion_count=delayed_count,
        out_of_order_ingestion_count=out_of_order_ingestion,
        findings=tuple(findings),
    )
