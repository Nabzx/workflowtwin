"""Command-line tests for synthetic generation and validation."""

from pathlib import Path

import pytest

from workflowtwin.cli.main import main
from workflowtwin.synthetic.artifacts import load_dataset


def _generate_arguments(directory: Path) -> list[str]:
    return [
        "generate",
        "--preset",
        "tiny",
        "--cases",
        "5",
        "--seed",
        "77",
        "--run-id",
        "cli-test-run",
        "--manifest-output",
        str(directory / "manifest.json"),
        "--ground-truth-output",
        str(directory / "ground-truth.json"),
        "--dataset-output",
        str(directory / "dataset.json"),
        "--validation-output",
        str(directory / "validation.json"),
    ]


def test_generate_cli_writes_revalidated_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(_generate_arguments(tmp_path))

    assert exit_code == 0
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "ground-truth.json").exists()
    assert (tmp_path / "validation.json").exists()
    dataset = load_dataset(tmp_path / "dataset.json")
    assert len(dataset.cases) == 5
    assert dataset.ground_truth.run_id == "cli-test-run"
    assert "Generated 5 fictional cases" in capsys.readouterr().out


def test_generate_cli_refuses_unsafe_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_generate_arguments(tmp_path)) == 0

    exit_code = main(_generate_arguments(tmp_path))

    assert exit_code == 1
    assert "artifact already exists" in capsys.readouterr().err


def test_validate_cli_loads_bundle_and_writes_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_generate_arguments(tmp_path)) == 0
    report_path = tmp_path / "independent-report.json"

    exit_code = main(
        [
            "validate",
            "--dataset",
            str(tmp_path / "dataset.json"),
            "--report-output",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert report_path.exists()
    assert "Validated 5 cases" in capsys.readouterr().out


def test_generate_cli_returns_nonzero_for_invalid_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "generate",
            "--cases",
            "0",
            "--manifest-output",
            str(tmp_path / "manifest.json"),
        ]
    )

    assert exit_code == 1
    assert "greater than or equal to 1" in capsys.readouterr().err
    assert not (tmp_path / "manifest.json").exists()
