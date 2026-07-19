"""Fictional pilot fixtures."""

import pytest
from tests.source_contracts.conftest import requirements as requirements
from tests.source_contracts.conftest import v2_source as v2_source

from workflowtwin.detector.models import supported_detector_metadata
from workflowtwin.pilot.models import PilotRecommendation
from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2

__all__ = ["pilot_recommendation", "requirements", "v2_source"]


@pytest.fixture
def pilot_recommendation(
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> PilotRecommendation:
    snapshot = v2_source[0][0]
    metadata = supported_detector_metadata()
    return PilotRecommendation(
        recommendation_id="pilot-recommendation-test",
        detector_evaluation_id="strict-v3-evaluation-test",
        case_id=snapshot.case_id,
        snapshot_id=snapshot.snapshot_id,
        detected_at=snapshot.available_at,
        missing_field_ids=("supporting_document",),
        source_references=(snapshot.snapshot_id, *snapshot.provenance_references),
        requirement_references=("supporting-document",),
        detector_product_name=metadata.product_name,
        supported_detector_fingerprint=metadata.supported_detector_fingerprint,
        original_detector_fingerprint=metadata.original_detector_fingerprint,
    )
