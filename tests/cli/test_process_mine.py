"""Command-line process reconstruction tests."""

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
                "process-cli-test",
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
        "process-mine",
        "--dataset",
        str(directory / "dataset.json"),
        "--manifest",
        str(directory / "manifest.json"),
        "--ground-truth",
        str(directory / "ground-truth.json"),
        "--minimum-cohort-size",
        "2",
        "--minimum-transition-frequency",
        "1",
        "--analysis-output",
        str(directory / "process.json"),
        "--report-output",
        str(directory / "process.md"),
        "--graph-output",
        str(directory / "graph.json"),
        "--case-output",
        str(directory / "cases.jsonl"),
    ]


def test_process_mine_cli_writes_safe_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _generate(tmp_path)
    capsys.readouterr()

    assert main(_arguments(tmp_path)) == 0

    output = capsys.readouterr().out
    assert "Process-mined 12 fictional cases" in output
    assert "Process fingerprint:" in output
    assert (tmp_path / "process.json").exists()
    assert (tmp_path / "process.md").exists()
    assert (tmp_path / "graph.json").exists()
    assert len((tmp_path / "cases.jsonl").read_text().splitlines()) == 12

    assert main(_arguments(tmp_path)) == 1
    assert "process artifact already exists" in capsys.readouterr().err


def test_database_process_mining_requires_run(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["process-mine", "--from-database"]) == 1
    assert "--generation-run is required" in capsys.readouterr().err
