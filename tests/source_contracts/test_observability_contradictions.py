"""Ceiling isolation, contradiction handling, and source evolution tests."""

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
from workflowtwin.source_contracts.observability import analyse_observability, contract_quality
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
