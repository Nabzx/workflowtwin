"""Cross-artifact validation and reproducibility tests."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from workflowtwin.opportunities.analyzer import OpportunityIdentifier
from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.models import OpportunityAnalysisInput


def test_incompatible_baseline_process_and_manifest_are_rejected(
    demo_opportunity_input: OpportunityAnalysisInput,
) -> None:
    wrong_process = demo_opportunity_input.process.model_copy(
        update={"source_dataset_fingerprint": "0" * 64}
    )
    with pytest.raises(ValueError, match="different dataset fingerprints"):
        OpportunityIdentifier(OpportunityConfig()).analyze(
            replace(demo_opportunity_input, process=wrong_process)
        )

    assert demo_opportunity_input.manifest is not None
    wrong_manifest = demo_opportunity_input.manifest.model_copy(
        update={"dataset_fingerprint": "0" * 64}
    )
    with pytest.raises(ValueError, match="manifest fingerprint"):
        OpportunityIdentifier(OpportunityConfig()).analyze(
            replace(demo_opportunity_input, manifest=wrong_manifest)
        )


def test_unsupported_analysis_version_is_rejected(
    demo_opportunity_input: OpportunityAnalysisInput,
) -> None:
    unsupported = demo_opportunity_input.process.model_copy(update={"analysis_version": "2.0.0"})

    with pytest.raises(ValueError, match="unsupported process analysis version"):
        OpportunityIdentifier(OpportunityConfig()).analyze(
            replace(demo_opportunity_input, process=unsupported)
        )


def test_fingerprint_is_stable_and_weight_sensitive(
    demo_opportunity_input: OpportunityAnalysisInput,
) -> None:
    fixed = datetime(2026, 7, 17, tzinfo=UTC)
    default = OpportunityIdentifier(OpportunityConfig()).analyze(
        demo_opportunity_input, analysed_at=fixed
    )
    repeated = OpportunityIdentifier(OpportunityConfig()).analyze(
        demo_opportunity_input, analysed_at=datetime(2030, 1, 1, tzinfo=UTC)
    )
    changed = OpportunityIdentifier(
        OpportunityConfig(
            value_weight=0.50,
            readiness_weight=0.20,
            confidence_weight=0.20,
            risk_weight=0.10,
        )
    ).analyze(demo_opportunity_input, analysed_at=fixed)

    assert default.opportunity_analysis_fingerprint == (repeated.opportunity_analysis_fingerprint)
    assert default.opportunity_analysis_fingerprint != (changed.opportunity_analysis_fingerprint)
    assert {item.opportunity_id for item in default.candidates} == {
        item.opportunity_id for item in changed.candidates
    }


def test_no_ground_truth_is_a_supported_not_evaluated_run(
    demo_opportunity_input: OpportunityAnalysisInput,
) -> None:
    analysis = OpportunityIdentifier(OpportunityConfig()).analyze(
        replace(demo_opportunity_input, ground_truth=None)
    )

    assert analysis.benchmark_evaluation.status == "not_evaluated"
    assert analysis.benchmark_evaluation.expected_count == 0
