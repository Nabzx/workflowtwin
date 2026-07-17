"""Simulation CLI success, overwrite, and invalid-input tests."""

from pathlib import Path

import pytest

from workflowtwin.cli.main import main
from workflowtwin.simulation.models import SimulationInput
from workflowtwin.synthetic.artifacts import (
    write_dataset,
    write_ground_truth,
    write_manifest,
)
from workflowtwin.synthetic.config import GenerationConfig
from workflowtwin.synthetic.models import GeneratedDataset


def _write_inputs(directory: Path, simulation_input: SimulationInput) -> list[str]:
    assert simulation_input.ground_truth is not None
    dataset = GeneratedDataset(
        config=GenerationConfig.model_validate(simulation_input.manifest.configuration),
        cases=simulation_input.source.cases,
        events=simulation_input.source.events,
        ground_truth=simulation_input.ground_truth,
        manifest=simulation_input.manifest,
    )
    write_dataset(directory / "dataset.json", dataset)
    write_manifest(directory / "manifest.json", simulation_input.manifest)
    write_ground_truth(directory / "ground-truth.json", simulation_input.ground_truth)
    (directory / "baseline.json").write_text(
        simulation_input.baseline.model_dump_json(), encoding="utf-8"
    )
    (directory / "process.json").write_text(
        simulation_input.process.model_dump_json(), encoding="utf-8"
    )
    (directory / "opportunities.json").write_text(
        simulation_input.opportunities.model_dump_json(), encoding="utf-8"
    )
    return [
        "simulate-intervention",
        "--dataset",
        str(directory / "dataset.json"),
        "--manifest",
        str(directory / "manifest.json"),
        "--baseline-analysis",
        str(directory / "baseline.json"),
        "--process-analysis",
        str(directory / "process.json"),
        "--opportunity-analysis",
        str(directory / "opportunities.json"),
        "--ground-truth",
        str(directory / "ground-truth.json"),
        "--scenario",
        "central",
        "--skip-sensitivity",
        "--analysis-output",
        str(directory / "simulation.json"),
        "--report-output",
        str(directory / "simulation.md"),
        "--comparison-output",
        str(directory / "comparison.json"),
        "--case-output",
        str(directory / "cases.jsonl"),
    ]


def test_cli_simulates_and_refuses_overwrite(
    tmp_path: Path,
    demo_simulation_input: SimulationInput,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = _write_inputs(tmp_path, demo_simulation_input)

    assert main(arguments) == 0
    output = capsys.readouterr().out
    assert "Selected opportunity: opportunity-7def8c82e8b589e5" in output
    assert "Scenario: central" in output
    assert "Simulation fingerprint:" in output
    assert (tmp_path / "simulation.json").exists()
    assert len((tmp_path / "cases.jsonl").read_text().splitlines()) == 1000

    assert main(arguments) == 1
    assert "simulation artifact already exists" in capsys.readouterr().err


def test_cli_rejects_missing_manifest_and_missing_database_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    common = [
        "--baseline-analysis",
        "missing-baseline.json",
        "--process-analysis",
        "missing-process.json",
        "--opportunity-analysis",
        "missing-opportunities.json",
    ]
    assert main(["simulate-intervention", "--dataset", "missing.json", *common]) == 1
    assert "--manifest is required" in capsys.readouterr().err
    assert main(["simulate-intervention", "--from-database", *common]) == 1
    assert "--generation-run is required" in capsys.readouterr().err
