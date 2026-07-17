"""Opportunity JSON, Markdown, graph, and safe overwrite tests."""

import json
from pathlib import Path

import pytest

from workflowtwin.opportunities.models import OpportunityAnalysis
from workflowtwin.opportunities.reporting import (
    OpportunityArtifactExistsError,
    write_opportunity_artifacts,
)


def test_artifacts_are_traceable_and_safe(
    tmp_path: Path, demo_opportunity_analysis: OpportunityAnalysis
) -> None:
    analysis_path = tmp_path / "analysis.json"
    report_path = tmp_path / "report.md"
    portfolio_path = tmp_path / "portfolio.json"
    evidence_path = tmp_path / "evidence.json"

    write_opportunity_artifacts(
        demo_opportunity_analysis,
        analysis_output=analysis_path,
        report_output=report_path,
        portfolio_output=portfolio_path,
        evidence_output=evidence_path,
        overwrite=False,
    )

    analysis = json.loads(analysis_path.read_text())
    report = report_path.read_text()
    assert analysis["opportunity_analysis_fingerprint"] == (
        demo_opportunity_analysis.opportunity_analysis_fingerprint
    )
    assert "Evidence chain" in report
    assert "does not authorise" in report
    assert "No LLM recommendation" in report
    assert len(json.loads(portfolio_path.read_text())) == 6
    network = json.loads(evidence_path.read_text())
    assert network["nodes"]
    assert network["links"]

    with pytest.raises(OpportunityArtifactExistsError):
        write_opportunity_artifacts(
            demo_opportunity_analysis,
            analysis_output=analysis_path,
            report_output=report_path,
            portfolio_output=portfolio_path,
            evidence_output=evidence_path,
            overwrite=False,
        )
