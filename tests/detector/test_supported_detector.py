"""Supported detector identity and delegation tests."""

from workflowtwin.detector import SUPPORTED_DETECTOR_NAME, CompletenessReviewDetector
from workflowtwin.shadow_v3.config import StrictV3Config
from workflowtwin.source_contracts.models import (
    AdministrativeTruthRecord,
    IncomingReferralSnapshotV2,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract


def test_supported_alias_delegates_to_unchanged_strict_v3(
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[AdministrativeTruthRecord, ...]],
    requirements: AdministrativeRequirementsContract,
) -> None:
    detector = CompletenessReviewDetector(requirements)
    run = detector.run(v2_source[0], run_id="supported-detector-test")
    lineage = detector.lineage
    assert lineage.product_name == SUPPORTED_DETECTOR_NAME
    assert lineage.derived_from == "strict-v3"
    assert lineage.original_detector_fingerprint == StrictV3Config().detector_fingerprint
    assert run.detector_fingerprint == lineage.original_detector_fingerprint
    assert lineage.supported_detector_fingerprint != lineage.original_detector_fingerprint
    assert lineage.recommendation_only is True
