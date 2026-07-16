"""Analysis report serialization and overwrite-safety tests."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.reporting import (
    AnalysisArtifactExistsError,
    write_analysis_artifacts,
)
from workflowtwin.services.baseline_analysis import input_from_dataset
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


def test_reports_are_inspectable_and_refuse_partial_overwrite(tmp_path: Path) -> None:
    dataset = SyntheticReferralGenerator(
        config_for_preset(GenerationPreset.TINY, seed=99, case_count=8),
        generated_at=datetime(2026, 7, 16, tzinfo=UTC),
    ).generate()
    analysis_input = input_from_dataset(dataset, ground_truth=dataset.ground_truth)
    bundle = BaselineAnalyzer(AnalysisConfig(minimum_cohort_size=2)).analyze(analysis_input)
    analysis_path = tmp_path / "analysis.json"
    report_path = tmp_path / "report.md"
    cases_path = tmp_path / "cases.jsonl"

    write_analysis_artifacts(
        bundle,
        analysis_output=analysis_path,
        report_output=report_path,
        case_metrics_output=cases_path,
    )

    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert payload["analysis_fingerprint"] == bundle.baseline.analysis_fingerprint
    assert "fictional" in report_path.read_text(encoding="utf-8").lower()
    assert len(cases_path.read_text(encoding="utf-8").splitlines()) == 8
    report_before = report_path.read_text(encoding="utf-8")
    with pytest.raises(AnalysisArtifactExistsError):
        write_analysis_artifacts(
            bundle,
            analysis_output=analysis_path,
            report_output=report_path,
            case_metrics_output=cases_path,
        )
    assert report_path.read_text(encoding="utf-8") == report_before
