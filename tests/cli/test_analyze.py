"""Command-line baseline analysis tests."""

from pathlib import Path

import pytest

from workflowtwin.cli.main import main


def _generate(directory: Path) -> None:
    assert (
        main(
            [
                "generate",
                "--preset",
                "tiny",
                "--cases",
                "12",
                "--seed",
                "42",
                "--run-id",
                "analysis-cli-test",
                "--manifest-output",
                str(directory / "manifest.json"),
                "--ground-truth-output",
                str(directory / "ground-truth.json"),
                "--dataset-output",
                str(directory / "dataset.json"),
            ]
        )
        == 0
    )


def _arguments(directory: Path) -> list[str]:
    return [
        "analyze",
        "--dataset",
        str(directory / "dataset.json"),
        "--manifest",
        str(directory / "manifest.json"),
        "--ground-truth",
        str(directory / "ground-truth.json"),
        "--minimum-cohort-size",
        "2",
        "--analysis-output",
        str(directory / "analysis.json"),
        "--report-output",
        str(directory / "report.md"),
        "--case-metrics-output",
        str(directory / "cases.jsonl"),
    ]


def test_analyze_cli_writes_outputs_and_completion_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _generate(tmp_path)
    capsys.readouterr()

    assert main(_arguments(tmp_path)) == 0

    output = capsys.readouterr().out
    assert "Analysed 12 fictional cases" in output
    assert "Analysis fingerprint:" in output
    assert (tmp_path / "analysis.json").exists()
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "cases.jsonl").exists()


def test_analyze_cli_refuses_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _generate(tmp_path)
    assert main(_arguments(tmp_path)) == 0
    capsys.readouterr()

    assert main(_arguments(tmp_path)) == 1
    assert "analysis artifact already exists" in capsys.readouterr().err


def test_database_analysis_requires_generation_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["analyze", "--from-database"]) == 1
    assert "--generation-run is required" in capsys.readouterr().err
