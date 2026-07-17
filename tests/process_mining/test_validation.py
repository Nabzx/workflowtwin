"""Configuration and cross-artifact process-analysis validation."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.domain.referrals.fixtures import straight_through_successful_referral
from workflowtwin.process_mining.analyzer import ProcessMiningAnalyzer
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.event_log import build_process_log
from workflowtwin.services.baseline_analysis import input_from_dataset
from workflowtwin.services.process_analysis import process_input_from_dataset
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset

from .conftest import input_for_scenarios


def test_invalid_process_configuration_is_rejected() -> None:
    now = datetime(2026, 7, 17, tzinfo=UTC)

    with pytest.raises(ValidationError, match="period_end"):
        ProcessMiningConfig(period_start=now, period_end=now - timedelta(hours=1))
    with pytest.raises(ValidationError, match="reference workflow"):
        ProcessMiningConfig(strict_reference_enabled=False, governed_reference_enabled=False)
    with pytest.raises(ValidationError, match="rare_variant_case_threshold"):
        ProcessMiningConfig(minimum_variant_frequency=1, rare_variant_case_threshold=2)
    with pytest.raises(ValidationError, match="duration_percentiles"):
        ProcessMiningConfig(duration_percentiles=(0.9, 0.5))
    with pytest.raises(ValidationError, match="timezone"):
        ProcessMiningConfig(reporting_timezone="Not/A-Timezone")


def test_unsupported_schema_trace_is_reported_and_excluded() -> None:
    scenario = straight_through_successful_referral()
    operational = input_for_scenarios((scenario,))
    unsupported = operational.cases[0].model_copy(update={"schema_version": 2})
    changed = operational.__class__(
        cases=(unsupported,),
        events=operational.events,
        dataset_fingerprint=operational.dataset_fingerprint,
        generation_run_id=None,
        manifest=None,
        ground_truth=None,
    )

    process_log = build_process_log(changed, ProcessMiningConfig(minimum_cohort_size=2))

    assert not process_log.traces
    assert process_log.quality.unsupported_schema_cases == 1
    assert "unsupported schema traces were excluded" in process_log.quality.warnings


def test_manifest_baseline_and_ground_truth_mismatches_are_rejected() -> None:
    dataset = SyntheticReferralGenerator(
        config_for_preset(GenerationPreset.TINY, seed=42, case_count=12),
        generated_at=datetime(2026, 7, 16, 12, tzinfo=UTC),
    ).generate()
    baseline = (
        BaselineAnalyzer(
            AnalysisConfig(
                source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
                generation_run_id=dataset.manifest.generation_run_id,
                minimum_cohort_size=2,
            )
        )
        .analyze(input_from_dataset(dataset))
        .baseline
    )
    config = ProcessMiningConfig(
        source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
        generation_run_id=dataset.manifest.generation_run_id,
        minimum_cohort_size=2,
    )

    wrong_manifest = dataset.manifest.model_copy(update={"dataset_fingerprint": "0" * 64})
    with pytest.raises(ValueError, match="fingerprint"):
        ProcessMiningAnalyzer(config).analyze(
            process_input_from_dataset(dataset, manifest=wrong_manifest)
        )

    wrong_baseline = baseline.model_copy(update={"source_dataset_fingerprint": "0" * 64})
    with pytest.raises(ValueError, match="baseline analysis source fingerprint"):
        ProcessMiningAnalyzer(config).analyze(
            process_input_from_dataset(dataset, baseline=wrong_baseline)
        )

    wrong_ground_truth = dataset.ground_truth.model_copy(update={"run_id": "other-run"})
    with pytest.raises(ValueError, match="ground truth generation run"):
        ProcessMiningAnalyzer(config).analyze(
            process_input_from_dataset(dataset, ground_truth=wrong_ground_truth)
        )
