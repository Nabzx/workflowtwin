"""Ceiling isolation, contradiction handling, and source evolution tests."""

from datetime import timedelta

from workflowtwin.shadow.fingerprint import shadow_id
from workflowtwin.shadow.models import ShadowEvaluationLabel, ShadowLabelStatus
from workflowtwin.source_contracts.contradictions import (
    ContradictionType,
    detect_snapshot_contradictions,
)
from workflowtwin.source_contracts.generator import v2_snapshot_fingerprint
from workflowtwin.source_contracts.models import (
    AdministrativeTruthRecord,
    IncomingReferralSnapshotV2,
)
from workflowtwin.source_contracts.observability import (
    MissedPositiveCategory,
    analyse_observability,
    contract_quality,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.states import AdministrativeFieldStateV2


def _labels(
    truth: tuple[AdministrativeTruthRecord, ...],
) -> tuple[ShadowEvaluationLabel, ...]:
    return tuple(
        ShadowEvaluationLabel(
            label_id=shadow_id("contract-test-label", item.case_id),
            case_id=item.case_id,
            valid_from=item.valid_from,
            status=(
                ShadowLabelStatus.NEGATIVE
                if item.supporting_document_present
                else ShadowLabelStatus.POSITIVE
            ),
            evidence_codes=("evaluation_only_truth",),
        )
        for item in truth
    )


def test_labels_do_not_change_source_projection(
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[AdministrativeTruthRecord, ...]],
    requirements: AdministrativeRequirementsContract,
) -> None:
    snapshots, truth = v2_source
    before = v2_snapshot_fingerprint(snapshots)
    analysis = analyse_observability(
        snapshots=snapshots,
        labels=_labels(truth),
        requirements=requirements,
    )
    assert analysis.total_hidden_positives > 0
    assert analysis.ceilings
    assert v2_snapshot_fingerprint(snapshots) == before
    quality = contract_quality(snapshots, requirements)
    assert 0 <= quality.usable_input_coverage <= 1


def test_not_applicable_missing_warning_is_a_contradiction(
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    snapshot = v2_source[0][0]
    fields = tuple(
        item.model_copy(
            update={
                "state": AdministrativeFieldStateV2.NOT_APPLICABLE,
                "applicable": False,
            }
        )
        if item.field_id == "supporting_document"
        else item
        for item in snapshot.fields
    )
    changed = snapshot.model_copy(
        update={
            "fields": fields,
            "source_warning_codes": ("supporting_document_missing",),
        }
    )
    contradictions = detect_snapshot_contradictions((changed,))
    assert contradictions[0].contradiction_type is (ContradictionType.NOT_APPLICABLE_WITH_WARNING)
    assert contradictions[0].requires_abstention is True


def test_producer_disagreement_and_warning_after_resolution_are_detected(
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    original = v2_source[0][0]
    present_fields = tuple(
        field.model_copy(update={"state": AdministrativeFieldStateV2.PRESENT})
        if field.field_id == "supporting_document"
        else field
        for field in original.fields
    )
    present = original.model_copy(
        update={"fields": present_fields, "producer_system": "producer-a"}
    )
    absent_fields = tuple(
        field.model_copy(update={"state": AdministrativeFieldStateV2.ABSENT})
        if field.field_id == "supporting_document"
        else field
        for field in original.fields
    )
    warning = original.model_copy(
        update={
            "snapshot_id": f"{original.snapshot_id}-warning",
            "available_at": original.available_at + timedelta(minutes=1),
            "fields": absent_fields,
            "source_warning_codes": ("supporting_document_missing",),
            "producer_system": "producer-b",
        }
    )
    kinds = {
        item.contradiction_type for item in detect_snapshot_contradictions((present, warning))
    }
    assert ContradictionType.PRODUCER_DISAGREEMENT in kinds
    assert ContradictionType.WARNING_AFTER_RESOLUTION in kinds


def test_taxonomy_is_complete_and_capacity_does_not_change_ceiling(
    v2_source: tuple[
        tuple[IncomingReferralSnapshotV2, ...], tuple[AdministrativeTruthRecord, ...]
    ],
    requirements: AdministrativeRequirementsContract,
) -> None:
    snapshots, truth = v2_source
    expected = {
        "source_evidence_unavailable",
        "evidence_arrived_too_late",
        "unknown_versus_absent_ambiguity",
        "conditional_applicability_unknown",
        "unsupported_form_contract",
        "stale_source_state",
        "conflicting_source_state",
        "confirmation_window_miss",
        "policy_abstention",
        "review_already_underway",
        "capacity_not_surfaced",
        "detector_rule_miss",
        "label_uncertainty",
    }
    assert {item.value for item in MissedPositiveCategory} == expected
    labels = _labels(truth)
    without_capacity = analyse_observability(
        snapshots=snapshots, labels=labels, requirements=requirements
    )
    all_cases = {item.case_id for item in snapshots}
    with_capacity = analyse_observability(
        snapshots=snapshots,
        labels=labels,
        requirements=requirements,
        surfaced_case_ids=all_cases,
    )
    first = without_capacity.ceilings[0]
    second = with_capacity.ceilings[0]
    assert first.contract_ceiling == second.contract_ceiling
    assert first.useful_time_ceiling == second.useful_time_ceiling
    assert first.surfaced_recall != second.surfaced_recall
