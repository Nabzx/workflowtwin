"""Strict-v3 evidence stability, lifecycle, authority, and leakage tests."""

from datetime import timedelta

from workflowtwin.shadow_v3.config import StrictV3Config
from workflowtwin.shadow_v3.detector import StrictV3Detector, verify_v3_audit
from workflowtwin.shadow_v3.models import V3Outcome, V3Run
from workflowtwin.source_contracts.models import (
    AdministrativeTruthRecord,
    IncomingReferralSnapshotV2,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.states import (
    AdministrativeFieldStateV2,
    ConflictStatus,
    FreshnessStatus,
    ManualReviewState,
    UpdateType,
)

V2Source = tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[AdministrativeTruthRecord, ...]]


def _with_support(
    snapshot: IncomingReferralSnapshotV2,
    state: AdministrativeFieldStateV2,
    *,
    applicable: bool | None = True,
) -> IncomingReferralSnapshotV2:
    return snapshot.model_copy(
        update={
            "fields": tuple(
                item.model_copy(update={"state": state, "applicable": applicable})
                if item.field_id == "supporting_document"
                else item
                for item in snapshot.fields
            )
        }
    )


def _run(
    snapshots: tuple[IncomingReferralSnapshotV2, ...],
    requirements: AdministrativeRequirementsContract,
) -> V3Run:
    return StrictV3Detector(StrictV3Config(), requirements).run(snapshots, run_id="strict-v3-unit")


def test_explicit_absent_recommends_and_unknown_abstains(
    v2_source: V2Source,
    requirements: AdministrativeRequirementsContract,
) -> None:
    base = v2_source[0][0]
    absent = _with_support(base, AdministrativeFieldStateV2.ABSENT).model_copy(
        update={
            "source_warning_codes": (),
            "manual_review_state": ManualReviewState.NOT_STARTED,
            "freshness": FreshnessStatus.FRESH,
            "conflict_status": ConflictStatus.NONE,
            "form_version": "NS-INTAKE-2",
            "requirements_contract_version": requirements.contract_version,
        }
    )
    assert _run((absent,), requirements).results[0].outcome is V3Outcome.RECOMMEND
    unknown = _with_support(absent, AdministrativeFieldStateV2.UNKNOWN)
    assert _run((unknown,), requirements).results[0].outcome is V3Outcome.ABSTAIN


def test_not_applicable_resolves_while_stale_and_conflicting_abstain(
    v2_source: V2Source,
    requirements: AdministrativeRequirementsContract,
) -> None:
    base = v2_source[0][0].model_copy(
        update={
            "form_version": "NS-INTAKE-2",
            "requirements_contract_version": requirements.contract_version,
            "freshness": FreshnessStatus.FRESH,
            "conflict_status": ConflictStatus.NONE,
        }
    )
    not_applicable = _with_support(
        base, AdministrativeFieldStateV2.NOT_APPLICABLE, applicable=False
    )
    assert _run((not_applicable,), requirements).results[0].outcome is (V3Outcome.NO_RECOMMENDATION)
    stale = base.model_copy(update={"freshness": FreshnessStatus.STALE})
    conflict = base.model_copy(update={"conflict_status": ConflictStatus.DETECTED})
    assert _run((stale,), requirements).results[0].outcome is V3Outcome.ABSTAIN
    assert _run((conflict,), requirements).results[0].outcome is V3Outcome.ABSTAIN


def test_pending_confirms_only_from_later_explicit_state(
    v2_source: V2Source,
    requirements: AdministrativeRequirementsContract,
) -> None:
    base = v2_source[0][0].model_copy(
        update={
            "form_version": "NS-INTAKE-2",
            "requirements_contract_version": requirements.contract_version,
            "freshness": FreshnessStatus.FRESH,
            "conflict_status": ConflictStatus.NONE,
        }
    )
    pending = _with_support(base, AdministrativeFieldStateV2.PENDING_SOURCE_UPDATE)
    pending_run = _run((pending,), requirements)
    assert [item.outcome for item in pending_run.results] == [
        V3Outcome.PENDING,
        V3Outcome.ABSTAIN,
    ]
    later = _with_support(pending, AdministrativeFieldStateV2.ABSENT).model_copy(
        update={
            "snapshot_id": "later-explicit-absence",
            "available_at": pending.available_at + timedelta(minutes=30),
            "source_record_version": pending.source_record_version + 1,
            "update_type": UpdateType.SUPERSESSION,
            "superseded_snapshot_id": pending.snapshot_id,
        }
    )
    outcomes = [item.outcome for item in _run((pending, later), requirements).results]
    assert outcomes == [V3Outcome.PENDING, V3Outcome.RECOMMEND]


def test_superseding_present_retracts_without_changing_earlier_decision(
    v2_source: V2Source,
    requirements: AdministrativeRequirementsContract,
) -> None:
    base = _with_support(v2_source[0][0], AdministrativeFieldStateV2.ABSENT).model_copy(
        update={
            "form_version": "NS-INTAKE-2",
            "requirements_contract_version": requirements.contract_version,
            "source_warning_codes": (),
            "manual_review_state": ManualReviewState.NOT_STARTED,
            "freshness": FreshnessStatus.FRESH,
            "conflict_status": ConflictStatus.NONE,
        }
    )
    earlier = _run((base,), requirements)
    present = _with_support(base, AdministrativeFieldStateV2.PRESENT).model_copy(
        update={
            "snapshot_id": "superseding-present",
            "available_at": base.available_at + timedelta(minutes=15),
            "source_record_version": base.source_record_version + 1,
            "update_type": UpdateType.SUPERSESSION,
            "superseded_snapshot_id": base.snapshot_id,
        }
    )
    replay = _run((base, present), requirements)
    assert replay.results[0] == earlier.results[0]
    assert replay.results[1].outcome is V3Outcome.RETRACT
    assert base.case_id in replay.retracted_case_ids


def test_manual_review_and_warning_are_observe_only_and_gp_is_not_a_rule(
    v2_source: V2Source,
    requirements: AdministrativeRequirementsContract,
) -> None:
    base = _with_support(v2_source[0][0], AdministrativeFieldStateV2.ABSENT).model_copy(
        update={
            "form_version": "NS-INTAKE-2",
            "requirements_contract_version": requirements.contract_version,
            "freshness": FreshnessStatus.FRESH,
            "conflict_status": ConflictStatus.NONE,
        }
    )
    review = base.model_copy(update={"manual_review_state": ManualReviewState.STARTED})
    warning = base.model_copy(
        update={
            "manual_review_state": ManualReviewState.NOT_STARTED,
            "source_warning_codes": ("supporting_document_missing",),
        }
    )
    assert _run((review,), requirements).results[0].outcome is V3Outcome.OBSERVE_ONLY
    assert _run((warning,), requirements).results[0].outcome is V3Outcome.OBSERVE_ONLY
    present = _with_support(base, AdministrativeFieldStateV2.PRESENT).model_copy(
        update={"source_warning_codes": (), "manual_review_state": ManualReviewState.NOT_STARTED}
    )
    assert _run((present,), requirements).results[0].outcome is V3Outcome.NO_RECOMMENDATION


def test_detector_preserves_source_and_builds_valid_audit_chain(
    v2_source: V2Source,
    requirements: AdministrativeRequirementsContract,
) -> None:
    snapshots = v2_source[0][:5]
    before = tuple(item.model_dump(mode="json") for item in snapshots)
    run = _run(snapshots, requirements)
    assert tuple(item.model_dump(mode="json") for item in snapshots) == before
    assert verify_v3_audit(run.audit_records) == (True, 0)
    assert all(item.recommendation_only for item in run.results)
