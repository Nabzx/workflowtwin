"""End-to-end file CLI coverage for shadow run, review, and evaluation."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from workflowtwin.cli.main import main
from workflowtwin.shadow.intake import generate_intake_artifacts, write_jsonl
from workflowtwin.synthetic.artifacts import write_dataset, write_manifest
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


def _source(directory: Path) -> dict[str, Path]:
    dataset = SyntheticReferralGenerator(
        config_for_preset(
            GenerationPreset.TINY,
            case_count=30,
            seed=9,
            generation_run_id="shadow-cli-source",
        ),
        generated_at=datetime(2026, 7, 18, tzinfo=UTC),
    ).generate()
    snapshots, labels = generate_intake_artifacts(dataset)
    paths = {
        key: directory / name
        for key, name in {
            "dataset": "dataset.json",
            "manifest": "manifest.json",
            "snapshots": "snapshots.jsonl",
            "labels": "labels.jsonl",
            "opportunity": "opportunity.json",
            "simulation": "simulation.json",
            "run": "run.json",
            "recommendations": "recommendations.jsonl",
            "audit": "audit.jsonl",
            "reviews": "reviews.jsonl",
            "evaluation": "evaluation.json",
            "report": "report.md",
            "visualisation": "visualisation.json",
        }.items()
    }
    write_dataset(paths["dataset"], dataset)
    write_manifest(paths["manifest"], dataset.manifest)
    write_jsonl(paths["snapshots"], snapshots)
    write_jsonl(paths["labels"], labels)
    paths["opportunity"].write_text(
        json.dumps({"opportunity_analysis_fingerprint": "opportunity-fingerprint"}),
        encoding="utf-8",
    )
    paths["simulation"].write_text(
        json.dumps({"simulation_analysis_fingerprint": "simulation-fingerprint"}),
        encoding="utf-8",
    )
    return paths


def _run_arguments(paths: dict[str, Path]) -> list[str]:
    return [
        "shadow-run",
        "--dataset",
        str(paths["dataset"]),
        "--manifest",
        str(paths["manifest"]),
        "--intake-snapshots",
        str(paths["snapshots"]),
        "--opportunity-analysis",
        str(paths["opportunity"]),
        "--simulation-analysis",
        str(paths["simulation"]),
        "--run-output",
        str(paths["run"]),
        "--recommendations-output",
        str(paths["recommendations"]),
        "--audit-output",
        str(paths["audit"]),
    ]


def test_shadow_cli_workflow_writes_validated_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _source(tmp_path)
    assert main(_run_arguments(paths)) == 0
    assert (
        main(
            [
                "shadow-review",
                "--run",
                str(paths["run"]),
                "--recommendations",
                str(paths["recommendations"]),
                "--benchmark-labels",
                str(paths["labels"]),
                "--validated-reviews-output",
                str(paths["reviews"]),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "shadow-evaluate",
                "--run",
                str(paths["run"]),
                "--recommendations",
                str(paths["recommendations"]),
                "--reviews",
                str(paths["reviews"]),
                "--audit",
                str(paths["audit"]),
                "--intake-snapshots",
                str(paths["snapshots"]),
                "--evaluation-labels",
                str(paths["labels"]),
                "--evaluation-output",
                str(paths["evaluation"]),
                "--report-output",
                str(paths["report"]),
                "--visualisation-output",
                str(paths["visualisation"]),
            ]
        )
        == 0
    )
    evaluation = json.loads(paths["evaluation"].read_text(encoding="utf-8"))
    assert evaluation["audit"]["chain_valid"] is True
    assert evaluation["policy"]["workflow_mutation_attempts"] == 0
    assert evaluation["evaluation_fingerprint"]
    assert "Shadow evaluation" in capsys.readouterr().out


def test_shadow_cli_refuses_overwrite_and_invalid_lineage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _source(tmp_path)
    assert main(_run_arguments(paths)) == 0
    assert main(_run_arguments(paths)) == 1
    assert "artifact already exists" in capsys.readouterr().err
    paths["opportunity"].write_text("{}", encoding="utf-8")
    changed = [*_run_arguments(paths), "--force"]
    assert main(changed) == 1
    assert "opportunity_analysis_fingerprint" in capsys.readouterr().err


def test_generate_cli_can_emit_separate_shadow_inputs(tmp_path: Path) -> None:
    snapshots = tmp_path / "generated-snapshots.jsonl"
    labels = tmp_path / "generated-labels.jsonl"
    assert (
        main(
            [
                "generate",
                "--preset",
                "tiny",
                "--cases",
                "5",
                "--run-id",
                "shadow-generation-cli",
                "--manifest-output",
                str(tmp_path / "manifest.json"),
                "--ground-truth-output",
                str(tmp_path / "ground-truth.json"),
                "--intake-snapshots-output",
                str(snapshots),
                "--shadow-labels-output",
                str(labels),
            ]
        )
        == 0
    )
    assert len(snapshots.read_text(encoding="utf-8").splitlines()) >= 5
    assert len(labels.read_text(encoding="utf-8").splitlines()) >= 5
