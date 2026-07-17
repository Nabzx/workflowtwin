"""Simulation report, JSON, comparison, JSONL, and overwrite tests."""

import json
from pathlib import Path

import pytest

from workflowtwin.simulation.models import SimulationAnalysis
from workflowtwin.simulation.reporting import (
    SimulationArtifactExistsError,
    write_simulation_artifacts,
)


def test_writes_traceable_artifacts_and_refuses_overwrite(
    tmp_path: Path,
    central_simulation_analysis: SimulationAnalysis,
) -> None:
    analysis_path = tmp_path / "analysis.json"
    report_path = tmp_path / "report.md"
    comparison_path = tmp_path / "comparison.json"
    case_path = tmp_path / "cases.jsonl"
    write_simulation_artifacts(
        central_simulation_analysis,
        analysis_output=analysis_path,
        report_output=report_path,
        comparison_output=comparison_path,
        case_output=case_path,
        overwrite=False,
    )

    payload = json.loads(analysis_path.read_text())
    report = report_path.read_text()
    assert payload["simulation_analysis_fingerprint"] == (
        central_simulation_analysis.simulation_analysis_fingerprint
    )
    assert "no production automation or realised impact" in report.lower()
    assert "Evidence chain" in report
    assert json.loads(comparison_path.read_text())["metric_comparison"]
    assert len(case_path.read_text().splitlines()) == 1000
    with pytest.raises(SimulationArtifactExistsError):
        write_simulation_artifacts(
            central_simulation_analysis,
            analysis_output=analysis_path,
            report_output=report_path,
            comparison_output=comparison_path,
            case_output=case_path,
            overwrite=False,
        )
