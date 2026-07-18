"""Online input, state, detector, and policy boundaries."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from workflowtwin.domain.referrals.enums import ReferralSource, ServiceLine, SourceSystem
from workflowtwin.shadow.config import DetectorProfile, ShadowConfig
from workflowtwin.shadow.detector import CompletenessReviewDetector
from workflowtwin.shadow.intake import generate_intake_artifacts, intake_snapshot_fingerprint
from workflowtwin.shadow.models import (
    AdministrativeFieldState,
    DetectorInput,
    DetectorOutcome,
    FieldAvailability,
    IncomingReferralSnapshot,
    PolicyStatus,
    ShadowEvaluationLabel,
)
from workflowtwin.shadow.policy import ShadowPolicy
from workflowtwin.shadow.runner import ShadowModeRunner
from workflowtwin.synthetic.models import GeneratedDataset

CASE_ID = UUID("11111111-1111-4111-8111-111111111111")


def _input(**changes: object) -> DetectorInput:
    values: dict[str, object] = {
        "case_id": CASE_ID,
        "as_of": datetime(2026, 7, 1, 9, tzinfo=UTC),
        "state_version": 1,
        "referral_source": ReferralSource.GP_PRACTICE,
        "requested_service_line": ServiceLine.CARDIOLOGY,
        "source_system": SourceSystem.REFERRAL_PORTAL,
        "form_version": "NS-INTAKE-2",
        "fields": AdministrativeFieldState(
            referral_form=FieldAvailability.PRESENT,
            supporting_document=FieldAvailability.PRESENT,
            source_acknowledgement=FieldAvailability.PRESENT,
            contact_route=FieldAvailability.PRESENT,
        ),
        "source_snapshot_ids": ("snapshot-1",),
    }
    values.update(changes)
    return DetectorInput.model_validate(values)


def _snapshot(
    at: datetime, version: int, supporting: FieldAvailability
) -> IncomingReferralSnapshot:
    return IncomingReferralSnapshot(
        snapshot_id=f"snapshot-{version}",
        case_id=CASE_ID,
        available_at=at,
        source_event_id=None,
        source_system=SourceSystem.REFERRAL_PORTAL,
        referral_source=ReferralSource.GP_PRACTICE,
        requested_service_line=ServiceLine.CARDIOLOGY,
        submitting_organisation_id="org-fictional",
        form_version="NS-INTAKE-2",
        source_record_version=version,
        referral_form=FieldAvailability.PRESENT,
        supporting_document=supporting,
        source_acknowledgement=FieldAvailability.PRESENT,
        contact_route=FieldAvailability.PRESENT,
    )


def test_intake_generation_is_separate_and_deterministic(
    tiny_shadow_source: tuple[
        GeneratedDataset,
        tuple[IncomingReferralSnapshot, ...],
        tuple[ShadowEvaluationLabel, ...],
    ],
) -> None:
    dataset, snapshots, labels = tiny_shadow_source
    assert isinstance(dataset, GeneratedDataset)
    repeated_snapshots, repeated_labels = generate_intake_artifacts(dataset)
    assert repeated_snapshots == snapshots
    assert repeated_labels == labels
    assert intake_snapshot_fingerprint(repeated_snapshots) == intake_snapshot_fingerprint(snapshots)
    assert dataset.manifest.dataset_fingerprint
    assert all(snapshot.is_synthetic for snapshot in repeated_snapshots)


def test_gp_source_alone_does_not_trigger(strict_shadow_config: ShadowConfig) -> None:
    config = strict_shadow_config
    policy = ShadowPolicy(config).evaluate(_input())
    result = CompletenessReviewDetector(config).evaluate(_input(), policy)
    assert policy.status is PolicyStatus.PERMITTED
    assert result.outcome is DetectorOutcome.NO_RECOMMENDATION


def test_profiles_apply_narrow_evidence_and_abstention(
    strict_shadow_config: ShadowConfig,
) -> None:
    config = strict_shadow_config
    unknown = _input(
        fields=_input().fields.model_copy(update={"supporting_document": FieldAvailability.UNKNOWN})
    )
    strict_result = CompletenessReviewDetector(config).evaluate(
        unknown, ShadowPolicy(config).evaluate(unknown)
    )
    balanced = config.model_copy(update={"detector_profile": DetectorProfile.BALANCED})
    missing_contact = _input(
        fields=_input().fields.model_copy(update={"contact_route": FieldAvailability.ABSENT})
    )
    balanced_result = CompletenessReviewDetector(balanced).evaluate(
        missing_contact, ShadowPolicy(balanced).evaluate(missing_contact)
    )
    exploratory = config.model_copy(update={"detector_profile": DetectorProfile.EXPLORATORY})
    exploratory_result = CompletenessReviewDetector(exploratory).evaluate(
        unknown, ShadowPolicy(exploratory).evaluate(unknown)
    )
    assert strict_result.outcome is DetectorOutcome.ABSTAIN
    assert balanced_result.outcome is DetectorOutcome.RECOMMEND
    assert exploratory_result.outcome is DetectorOutcome.RECOMMEND


def test_unsupported_form_requires_abstention(strict_shadow_config: ShadowConfig) -> None:
    config = strict_shadow_config
    unsupported = _input(form_version="UNKNOWN")
    policy = ShadowPolicy(config).evaluate(unsupported)
    result = CompletenessReviewDetector(config).evaluate(unsupported, policy)
    assert policy.status is PolicyStatus.ABSTAIN_REQUIRED
    assert result.outcome is DetectorOutcome.ABSTAIN


def test_source_availability_controls_replay_and_retraction(
    strict_shadow_config: ShadowConfig,
) -> None:
    start = datetime(2026, 7, 1, 9, tzinfo=UTC)
    correction = _snapshot(start + timedelta(hours=1), 2, FieldAvailability.PRESENT)
    initial = _snapshot(start, 1, FieldAvailability.ABSENT)
    run = ShadowModeRunner(strict_shadow_config).run((correction, initial))
    assert [item.status.value for item in run.recommendations] == ["created", "retracted"]
    assert run.detector_results[0].evaluated_at == start
    assert run.detector_results[1].evaluated_at == start + timedelta(hours=1)


def test_future_snapshot_is_not_visible_at_cutoff(strict_shadow_config: ShadowConfig) -> None:
    start = datetime(2026, 7, 1, 9, tzinfo=UTC)
    initial = _snapshot(start, 1, FieldAvailability.ABSENT)
    future_a = _snapshot(start + timedelta(hours=1), 2, FieldAvailability.PRESENT)
    future_b = _snapshot(start + timedelta(hours=1), 2, FieldAvailability.UNKNOWN)
    first_a = ShadowModeRunner(strict_shadow_config).run((initial, future_a), max_source_items=1)
    first_b = ShadowModeRunner(strict_shadow_config).run((initial, future_b), max_source_items=1)
    assert first_a.detector_results == first_b.detector_results
    assert first_a.recommendations == first_b.recommendations


def test_unchanged_recommendation_is_suppressed_then_expires(
    strict_shadow_config: ShadowConfig,
) -> None:
    start = datetime(2026, 7, 1, 9, tzinfo=UTC)
    initial = _snapshot(start, 1, FieldAvailability.ABSENT)
    unchanged = _snapshot(start + timedelta(minutes=5), 2, FieldAvailability.ABSENT)
    later = _snapshot(start + timedelta(hours=9), 3, FieldAvailability.ABSENT).model_copy(
        update={"case_id": UUID("22222222-2222-4222-8222-222222222222")}
    )
    run = ShadowModeRunner(strict_shadow_config).run((initial, unchanged, later))
    statuses = [item.status.value for item in run.recommendations if item.case_id == CASE_ID]
    assert statuses == ["created", "unchanged", "expired"]


def test_clinical_fields_are_rejected_at_detector_boundary() -> None:
    values = _input().model_dump(mode="python")
    values["diagnosis"] = "not permitted"
    try:
        DetectorInput.model_validate(values)
    except ValueError as error:
        assert "Extra inputs are not permitted" in str(error)
    else:
        raise AssertionError("clinical input must not enter DetectorInput")
