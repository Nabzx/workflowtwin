"""CLI tests for the supported detector, pilot, and demo paths."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from workflowtwin.cli.main import _parser, main
from workflowtwin.pilot.pipeline import run_supported_analysis_pipeline
from workflowtwin.synthetic.artifacts import write_dataset
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


def _dataset(path: Path) -> Path:
    dataset = SyntheticReferralGenerator(
        config_for_preset(
            GenerationPreset.TINY,
            case_count=12,
            seed=9,
            generation_run_id="supported-cli-source",
        ),
        generated_at=datetime(2026, 7, 19, tzinfo=UTC),
    ).generate()
    write_dataset(path, dataset)
    return path


def test_supported_shadow_run_uses_v2_alias(tmp_path: Path) -> None:
    output = tmp_path / "supported-shadow.json"
    assert (
        main(
            [
                "shadow-run",
                "--dataset",
                str(_dataset(tmp_path / "dataset.json")),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["intake_contract"] == "Northstar intake contract"
    assert payload["detector"]["product_name"] == "completeness-review-detector-v1"
    assert payload["detector"]["derived_from"] == "strict-v3"
    assert (
        payload["run"]["detector_fingerprint"]
        == payload["detector"]["original_detector_fingerprint"]
    )
    assert (
        main(["shadow-run", "--dataset", str(tmp_path / "dataset.json"), "--output", str(output)])
        == 1
    )


def test_pilot_and_demo_commands_write_compact_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pilot = tmp_path / "pilot"
    assert main(["pilot-run", "--output-dir", str(pilot)]) == 0
    payload = json.loads((pilot / "pilot-run.json").read_text(encoding="utf-8"))
    assert payload["assessment"] == "ready_for_fictional_pilot_demo"
    assert payload["metrics"]["external_communication_attempts"] == 0
    assert "No message was sent" in capsys.readouterr().out

    demo = tmp_path / "demo"
    assert main(["demo", "--output-dir", str(demo), "--skip-heavy-analysis"]) == 0
    seed = json.loads((demo / "demo-seed.json").read_text(encoding="utf-8"))
    assert seed["api_command"] == "uv run workflowtwin serve"
    assert seed["no_message_sent"] is True
    assert main(["demo", "--output-dir", str(demo)]) == 1
    assert main(["demo", "--output-dir", str(demo), "--reset"]) == 0


def test_main_help_excludes_historical_experiment_commands() -> None:
    help_text = _parser().format_help()
    for supported in ("demo", "shadow-run", "pilot-run", "serve"):
        assert supported in help_text
    for obsolete in (
        "shadow-review",
        "shadow-evaluate",
        "shadow-refine",
        "shadow-holdout",
        "shadow-v3-develop",
        "shadow-v3-validate",
        "shadow-v3-holdout",
        "source-contract-build",
    ):
        assert obsolete not in help_text


def test_supported_analysis_pipeline_reaches_counterfactual_simulation() -> None:
    result = run_supported_analysis_pipeline()
    assert result["heavy_analysis_completed"] is True
    assert result["fictional_case_count"] == 1000
    for stage in ("baseline", "process", "opportunity", "simulation"):
        assert len(str(result[f"{stage}_analysis_fingerprint"])) == 64


def test_generate_emits_supported_v2_intake(tmp_path: Path) -> None:
    snapshots = tmp_path / "northstar-intake.jsonl"
    assert (
        main(
            [
                "generate",
                "--preset",
                "tiny",
                "--cases",
                "5",
                "--run-id",
                "supported-generation-cli",
                "--manifest-output",
                str(tmp_path / "manifest.json"),
                "--ground-truth-output",
                str(tmp_path / "ground-truth.json"),
                "--intake-snapshots-output",
                str(snapshots),
            ]
        )
        == 0
    )
    first = json.loads(snapshots.read_text(encoding="utf-8").splitlines()[0])
    assert first["schema_version"] == 2
    assert first["requirements_contract_version"]
