"""Opportunity-identification CLI success and failure tests."""

from pathlib import Path

import pytest

from workflowtwin.cli.main import main
from workflowtwin.opportunities.models import OpportunityAnalysisInput


def _write_inputs(directory: Path, analysis_input: OpportunityAnalysisInput) -> None:
    directory.joinpath("baseline.json").write_text(
        analysis_input.baseline.model_dump_json(), encoding="utf-8"
    )
    directory.joinpath("process.json").write_text(
        analysis_input.process.model_dump_json(), encoding="utf-8"
    )
    assert analysis_input.manifest is not None
    assert analysis_input.ground_truth is not None
    directory.joinpath("manifest.json").write_text(
        analysis_input.manifest.model_dump_json(), encoding="utf-8"
    )
    directory.joinpath("ground-truth.json").write_text(
        analysis_input.ground_truth.model_dump_json(), encoding="utf-8"
    )


def _arguments(directory: Path) -> list[str]:
    return [
        "identify-opportunities",
        "--baseline-analysis",
        str(directory / "baseline.json"),
        "--process-analysis",
        str(directory / "process.json"),
        "--research-pack",
        "data/research/northstar-research-v1.json",
        "--manifest",
        str(directory / "manifest.json"),
        "--ground-truth",
        str(directory / "ground-truth.json"),
        "--analysis-output",
        str(directory / "opportunities.json"),
        "--report-output",
        str(directory / "opportunities.md"),
        "--portfolio-output",
        str(directory / "portfolio.json"),
        "--evidence-output",
        str(directory / "evidence.json"),
    ]


def test_cli_writes_portfolio_and_refuses_overwrite(
    tmp_path: Path,
    demo_opportunity_input: OpportunityAnalysisInput,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_inputs(tmp_path, demo_opportunity_input)

    assert main(_arguments(tmp_path)) == 0
    output = capsys.readouterr().out
    assert "Candidates: 7 before deduplication; 6 after" in output
    assert "benchmark: 4/4" in output
    assert "Opportunity fingerprint:" in output
    assert (tmp_path / "opportunities.json").exists()

    assert main(_arguments(tmp_path)) == 1
    assert "opportunity artifact already exists" in capsys.readouterr().err


def test_cli_rejects_missing_input(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "identify-opportunities",
                "--baseline-analysis",
                "missing.json",
                "--process-analysis",
                "missing.json",
                "--research-pack",
                "missing.json",
            ]
        )
        == 1
    )
    assert "No such file" in capsys.readouterr().err
