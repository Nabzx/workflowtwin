"""Confirmation, as-of awareness, and capacity separation tests."""

from datetime import UTC, datetime, timedelta

import pytest

from tests.shadow.conftest import ShadowSource
from workflowtwin.shadow.intake import generate_intake_artifacts
from workflowtwin.shadow.models import FieldAvailability
from workflowtwin.shadow_refinement.capacity import (
    apply_capacity,
    build_queue_checkpoint,
    validate_queue_checkpoint,
)
from workflowtwin.shadow_refinement.config import CAPACITY_CONFIGS, CapacityProfile
from workflowtwin.shadow_refinement.detector import StrictV2Detector
from workflowtwin.shadow_refinement.models import (
    ConfirmationStatus,
    PriorityLevel,
    QueueStatus,
    RefinementContext,
)
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


@pytest.fixture
def tiny_shadow_source() -> ShadowSource:
    dataset = SyntheticReferralGenerator(
        config_for_preset(
            GenerationPreset.TINY,
            case_count=40,
            seed=42,
            generation_run_id="refinement-test-source",
        ),
        generated_at=datetime(2026, 7, 18, tzinfo=UTC),
    ).generate()
    snapshots, labels = generate_intake_artifacts(dataset)
    return dataset, snapshots, labels


def test_confirmation_window_resolves_transient_absence(
    tiny_shadow_source: ShadowSource,
) -> None:
    first = tiny_shadow_source[1][0].model_copy(
        update={
            "supporting_document": FieldAvailability.ABSENT,
            "form_version": "NS-INTAKE-2",
            "source_record_version": 1,
        }
    )
    correction = first.model_copy(
        update={
            "snapshot_id": f"{first.snapshot_id}-correction",
            "available_at": first.available_at + timedelta(minutes=60),
            "source_record_version": 2,
            "supporting_document": FieldAvailability.PRESENT,
        }
    )
    signal = StrictV2Detector().run((first, correction))[0]
    assert signal.status is ConfirmationStatus.RESOLVED
    assert signal.additional_latency_minutes == 60


def test_explicit_review_context_is_observe_only(tiny_shadow_source: ShadowSource) -> None:
    first = tiny_shadow_source[1][0].model_copy(
        update={"supporting_document": FieldAvailability.ABSENT, "form_version": "NS-INTAKE-2"}
    )
    context = RefinementContext(snapshot_id=first.snapshot_id, manual_review_started=True)
    signal = StrictV2Detector().run((first,), contexts={first.snapshot_id: context})[0]
    assert signal.status is ConfirmationStatus.CONFIRMED
    assert signal.priority is PriorityLevel.OBSERVE_ONLY
    assert "manual_review_already_started" in signal.reason_codes


def test_capacity_does_not_change_detector_positive_count(
    tiny_shadow_source: ShadowSource,
) -> None:
    first = tiny_shadow_source[1][0].model_copy(
        update={"supporting_document": FieldAvailability.ABSENT, "form_version": "NS-INTAKE-2"}
    )
    second = tiny_shadow_source[1][1].model_copy(
        update={
            "case_id": tiny_shadow_source[0].cases[1].id,
            "snapshot_id": "capacity-second",
            "available_at": first.available_at,
            "supporting_document": FieldAvailability.ABSENT,
            "form_version": "NS-INTAKE-2",
            "source_record_version": 1,
        }
    )
    signals = StrictV2Detector().run((first, second))
    config = CAPACITY_CONFIGS[CapacityProfile.STRESS].model_copy(
        update={"maximum_recommendations_per_day": 1, "review_minutes_available_per_day": 5}
    )
    events, metrics = apply_capacity(signals, config)
    assert metrics.detector_positive_cases == 2
    assert metrics.surfaced_recommendations == 1
    assert metrics.deferred_recommendations == 1
    assert any(item.status is QueueStatus.DEFERRED for item in events)
    checkpoint = build_queue_checkpoint(
        run_id="capacity-test",
        signals=signals,
        events=events,
        detector_fingerprint=StrictV2Detector().config.detector_fingerprint,
        config=config,
    )
    validate_queue_checkpoint(
        checkpoint,
        detector_fingerprint=StrictV2Detector().config.detector_fingerprint,
        config=config,
    )
