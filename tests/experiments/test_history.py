"""Compact regression checks for immutable detector experiment evidence."""

from pathlib import Path

import pytest

from workflowtwin.experiments.history import load_detector_golden

FIXTURES = Path("tests/fixtures/experiments")


@pytest.mark.parametrize(
    ("name", "assessment"),
    [
        ("strict-v1", "do_not_promote"),
        ("strict-v2", "do_not_promote"),
        ("strict-v3", "strict_v3_validation_failed"),
    ],
)
def test_historical_detector_golden_is_readable_and_consistent(name: str, assessment: str) -> None:
    golden = load_detector_golden(FIXTURES / f"{name}.json")
    assert golden.detector_version == name
    assert golden.assessment_result == assessment
    assert golden.fictional is True
    assert golden.recommendation_identifiers
    assert len(set(golden.recommendation_identifiers)) == len(golden.recommendation_identifiers)
    assert golden.headline_metrics.detector_positive_coverage == (
        golden.headline_metrics.detector_positives / golden.headline_metrics.incoming_cases
    )
