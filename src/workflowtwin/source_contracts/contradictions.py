"""Administrative source contradiction detection and abstention evidence."""

from collections import Counter
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2, SourceContractModel
from workflowtwin.source_contracts.states import AdministrativeFieldStateV2, ManualReviewState


class ContradictionType(StrEnum):
    FIELD_ABSENT_DOCUMENT_PRESENT = "field_absent_document_present"
    NOT_APPLICABLE_WITH_WARNING = "not_applicable_with_missing_warning"
    NON_MONOTONIC_SUPERSESSION = "non_monotonic_supersession"
    REVIEW_COMPLETE_BEFORE_AVAILABILITY = "review_complete_before_availability"
    WARNING_AFTER_RESOLUTION = "warning_after_resolution"
    PRODUCER_DISAGREEMENT = "producer_disagreement"


class SourceContradiction(SourceContractModel):
    contradiction_type: ContradictionType
    case_id: UUID
    snapshot_ids: tuple[str, ...]
    source_systems: tuple[str, ...]
    resolution_policy: str
    requires_abstention: bool
    estimated_review_minutes: float = Field(default=4, ge=0)


def detect_snapshot_contradictions(
    snapshots: tuple[IncomingReferralSnapshotV2, ...],
) -> tuple[SourceContradiction, ...]:
    results = []
    by_case: dict[UUID, list[IncomingReferralSnapshotV2]] = {}
    for snapshot in snapshots:
        by_case.setdefault(snapshot.case_id, []).append(snapshot)
        support = snapshot.field("supporting_document")
        if (
            support is not None
            and support.state is AdministrativeFieldStateV2.NOT_APPLICABLE
            and ("supporting_document_missing" in snapshot.source_warning_codes)
        ):
            results.append(
                SourceContradiction(
                    contradiction_type=ContradictionType.NOT_APPLICABLE_WITH_WARNING,
                    case_id=snapshot.case_id,
                    snapshot_ids=(snapshot.snapshot_id,),
                    source_systems=(snapshot.source_system.value,),
                    resolution_policy="abstain_and_request_administrative_verification",
                    requires_abstention=True,
                )
            )
        if (
            snapshot.manual_review_state is ManualReviewState.COMPLETED
            and snapshot.source_event_at > snapshot.available_at
        ):
            results.append(
                SourceContradiction(
                    contradiction_type=ContradictionType.REVIEW_COMPLETE_BEFORE_AVAILABILITY,
                    case_id=snapshot.case_id,
                    snapshot_ids=(snapshot.snapshot_id,),
                    source_systems=(snapshot.source_system.value,),
                    resolution_policy="reject_invalid_source_timeline",
                    requires_abstention=True,
                )
            )
    for case_id, case_snapshots in by_case.items():
        ordered = sorted(case_snapshots, key=lambda item: (item.available_at, item.snapshot_id))
        previous = None
        for snapshot in ordered:
            if previous and snapshot.source_record_version < previous.source_record_version:
                results.append(
                    SourceContradiction(
                        contradiction_type=ContradictionType.NON_MONOTONIC_SUPERSESSION,
                        case_id=case_id,
                        snapshot_ids=(previous.snapshot_id, snapshot.snapshot_id),
                        source_systems=(previous.source_system.value, snapshot.source_system.value),
                        resolution_policy="retain_newer_version_and_abstain_on_disputed_field",
                        requires_abstention=True,
                    )
                )
            previous = snapshot
    return tuple(results)


def contradiction_counts(
    contradictions: tuple[SourceContradiction, ...],
) -> dict[str, int]:
    return dict(sorted(Counter(item.contradiction_type.value for item in contradictions).items()))
