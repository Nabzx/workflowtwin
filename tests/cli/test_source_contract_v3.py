"""File CLI coverage for source analysis and gated strict-v3 evaluation."""

import json
from datetime import UTC, datetime
from pathlib import Path

from workflowtwin.cli.main import main
from workflowtwin.shadow_refinement.models import DatasetRole, DatasetSpecification
from workflowtwin.shadow_refinement.protocol import load_refinement_protocol, write_protocol
from workflowtwin.shadow_v3.models import (
    SourceQualityGates,
    V3DatasetRole,
    V3DatasetSpecification,
    V3Thresholds,
)
from workflowtwin.shadow_v3.protocol import load_v3_protocol, write_v3_protocol
from workflowtwin.source_contracts.io import load_v2_jsonl
from workflowtwin.synthetic.artifacts import write_dataset
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


def _old_spec(dataset_id: str, role: DatasetRole, seed: int) -> DatasetSpecification:
    return DatasetSpecification(
        dataset_id=dataset_id,
        role=role,
        seed=seed,
        case_count=30,
        operating_days=20,
        generation_run_id=f"cli-{dataset_id}",
    )


def _v3_spec(dataset_id: str, role: V3DatasetRole, seed: int) -> V3DatasetSpecification:
    return V3DatasetSpecification(
        dataset_id=dataset_id,
        role=role,
        seed=seed,
        case_count=40,
        operating_days=20,
        generation_run_id=f"cli-{dataset_id}",
    )


def test_source_contract_analysis_and_safe_overwrite(tmp_path: Path) -> None:
    source = load_refinement_protocol(Path("config/shadow/refinement-protocol.json"))
    protocol = source.model_copy(
        update={
            "protocol_id": "source-cli-test",
            "development_datasets": (
                _old_spec("source-development", DatasetRole.DEVELOPMENT, 31),
            ),
            "validation_datasets": (
                _old_spec("source-validation", DatasetRole.VALIDATION, 32),
            ),
            "holdout_dataset": _old_spec("unused-holdout", DatasetRole.HOLDOUT, 33),
        }
    )
    protocol_path = tmp_path / "source-protocol.json"
    write_protocol(protocol_path, protocol)
    analysis = tmp_path / "analysis.json"
    report = tmp_path / "analysis.md"
    command = [
        "shadow-analyse-misses",
        "--protocol",
        str(protocol_path),
        "--analysis-output",
        str(analysis),
        "--report-output",
        str(report),
    ]
    assert main(command) == 0
    assert main(command) == 1
    payload = json.loads(analysis.read_text(encoding="utf-8"))
    assert payload["recommendations_generated"] == 0
    assert payload["previous_holdout_usage"].startswith("aggregate_preservation_only")

    validation = tmp_path / "contract-validation.json"
    assert (
        main(
            [
                "source-contract-validate",
                "--validation-output",
                str(validation),
            ]
        )
        == 0
    )
    assert json.loads(validation.read_text(encoding="utf-8"))["clinical_fields_permitted"] is False


def test_source_contract_build_separates_snapshot_jsonl_from_truth(tmp_path: Path) -> None:
    dataset = SyntheticReferralGenerator(
        config_for_preset(
            GenerationPreset.TINY,
            case_count=12,
            seed=34,
            generation_run_id="source-build-cli-test",
        ),
        generated_at=datetime(2026, 7, 18, tzinfo=UTC),
    ).generate()
    dataset_path = tmp_path / "dataset.json"
    snapshots_path = tmp_path / "snapshots.jsonl"
    truth_path = tmp_path / "truth.json"
    validation_path = tmp_path / "validation.json"
    write_dataset(dataset_path, dataset)
    command = [
        "source-contract-build",
        "--dataset",
        str(dataset_path),
        "--snapshots-output",
        str(snapshots_path),
        "--truth-output",
        str(truth_path),
        "--validation-output",
        str(validation_path),
    ]
    assert main(command) == 0
    assert main(command) == 1
    snapshots = load_v2_jsonl(snapshots_path)
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    assert snapshots
    assert truth["detector_access_permitted"] is False
    assert "supporting_document_present" not in snapshots_path.read_text(encoding="utf-8")
    assert json.loads(validation_path.read_text(encoding="utf-8"))["is_valid"] is True


def test_strict_v3_cli_lock_and_single_use_holdout(tmp_path: Path) -> None:
    source = load_v3_protocol(Path("config/shadow/strict-v3-protocol.json"))
    protocol = source.model_copy(
        update={
            "protocol_id": "v3-cli-test",
            "development_datasets": (
                _v3_spec("v3-development", V3DatasetRole.DEVELOPMENT, 41),
            ),
            "validation_dataset": _v3_spec(
                "v3-validation", V3DatasetRole.VALIDATION, 42
            ),
            "holdout_dataset": _v3_spec("v3-holdout", V3DatasetRole.HOLDOUT, 43),
            "thresholds": V3Thresholds(
                minimum_precision=0,
                minimum_recall=0,
                minimum_ceiling_relative_recall=0,
                maximum_false_positive_hours_per_100_cases=100,
                maximum_detector_positive_coverage=1,
                maximum_surfaced_coverage=1,
                maximum_p95_recommendation_latency_minutes=1000,
                minimum_audit_completeness=1,
                minimum_policy_compliance=1,
            ),
            "source_quality_gates": SourceQualityGates(
                minimum_supported_form_rate=0,
                minimum_applicability_coverage=0,
                minimum_requirements_version_agreement=0,
                minimum_usable_input_coverage=0,
                maximum_stale_snapshot_rate=1,
                maximum_conflict_rate=1,
            ),
        }
    )
    protocol_path = tmp_path / "v3-protocol.json"
    output = tmp_path / "v3"
    write_v3_protocol(protocol_path, protocol)
    base = ["--protocol", str(protocol_path), "--output-dir", str(output)]
    assert main(["shadow-v3-develop", *base]) == 0
    assert main(["shadow-v3-validate", *base]) == 0
    assert main(["shadow-v3-holdout", *base]) == 0
    assert main(["shadow-v3-holdout", *base]) == 0
    registry = json.loads((output / "holdout-registry.json").read_text(encoding="utf-8"))
    assert registry["evaluation_count"] == 1
    assert registry["status"] == "completed"
