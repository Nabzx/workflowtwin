"""Strict-v3 development, validation, locking, holdout, and comparison service."""

import json
from pathlib import Path
from uuid import UUID

from workflowtwin.shadow.intake import intake_snapshot_fingerprint
from workflowtwin.shadow.models import ShadowEvaluationLabel, ShadowLabelStatus
from workflowtwin.shadow_refinement.config import StrictV2Config
from workflowtwin.shadow_refinement.evaluation import evaluate_v1, evaluate_v2
from workflowtwin.shadow_refinement.models import (
    BenchmarkDatasetManifest,
    DatasetRole,
    RefinementThresholds,
)
from workflowtwin.shadow_v3.benchmark import build_v3_dataset
from workflowtwin.shadow_v3.config import StrictV3Config
from workflowtwin.shadow_v3.evaluation import evaluate_v3
from workflowtwin.shadow_v3.models import (
    StrictV3Lock,
    StrictV3Protocol,
    V3DatasetSpecification,
    V3Evaluation,
)
from workflowtwin.shadow_v3.protocol import (
    begin_v3_holdout,
    complete_v3_holdout,
    lock_after_validation,
    validate_protocol_locks,
)
from workflowtwin.shadow_v3.reporting import render_v3_report
from workflowtwin.source_contracts.io import write_json
from workflowtwin.source_contracts.models import SourceContractDefinition
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.validation import validate_snapshots


def _evaluate_specification(
    *,
    specification: V3DatasetSpecification,
    protocol: StrictV3Protocol,
    config: StrictV3Config,
    definition: SourceContractDefinition,
    requirements: AdministrativeRequirementsContract,
) -> tuple[V3Evaluation, dict[str, object]]:
    dataset, v1, v2, _truth, labels, manifest = build_v3_dataset(specification, requirements)
    validation = validate_snapshots(v2, definition=definition, requirements=requirements)
    if not validation.is_valid:
        raise ValueError(f"invalid V2 source publication for {specification.dataset_id}")
    evaluation = evaluate_v3(
        protocol=protocol,
        config=config,
        requirements=requirements,
        manifest=manifest,
        snapshots=v2,
        labels=labels,
    )
    initial_labels: dict[UUID, ShadowEvaluationLabel] = {}
    for label in labels:
        initial_labels.setdefault(label.case_id, label)
    comparison_manifest = BenchmarkDatasetManifest(
        dataset_id=f"{specification.dataset_id}-controlled-comparison",
        role=DatasetRole.VALIDATION,
        seed=specification.seed,
        case_count=specification.case_count,
        dataset_fingerprint=dataset.manifest.dataset_fingerprint,
        snapshot_fingerprint=intake_snapshot_fingerprint(v1),
        source_mix=manifest.source_mix,
        form_version_mix=manifest.form_version_mix,
        positive_prevalence=(
            sum(item.status is ShadowLabelStatus.POSITIVE for item in initial_labels.values())
            / specification.case_count
        ),
        data_quality_conditions={
            "v2_snapshots": len(v2),
            "v2_contract_warnings": sum(item.count for item in validation.findings),
        },
    )
    old_thresholds = RefinementThresholds()
    v1_evaluation = evaluate_v1(
        manifest=comparison_manifest,
        snapshots=v1,
        labels=labels,
        thresholds=old_thresholds,
    )
    v2_evaluation = evaluate_v2(
        manifest=comparison_manifest,
        snapshots=v1,
        labels=labels,
        config=StrictV2Config(),
        thresholds=old_thresholds,
    )
    comparison: dict[str, object] = {
        "comparison_scope": "controlled new split; not an exact cross-holdout causal comparison",
        "strict_v1": v1_evaluation.detector.model_dump(mode="json"),
        "strict_v2": v2_evaluation.detector.model_dump(mode="json"),
        "strict_v3": evaluation.detector.model_dump(mode="json"),
        "source_contracts": {
            "strict_v1": "incoming-referral-snapshot-v1",
            "strict_v2": "incoming-referral-snapshot-v1",
            "strict_v3": config.source_contract_version,
        },
    }
    return evaluation, comparison


def run_v3_development(
    *,
    protocol: StrictV3Protocol,
    config: StrictV3Config,
    definition: SourceContractDefinition,
    requirements: AdministrativeRequirementsContract,
    output_path: Path,
    report_path: Path,
    overwrite: bool = False,
) -> tuple[V3Evaluation, ...]:
    validate_protocol_locks(protocol, config)
    evaluations = []
    comparisons = []
    for specification in protocol.development_datasets:
        evaluation, comparison = _evaluate_specification(
            specification=specification,
            protocol=protocol,
            config=config,
            definition=definition,
            requirements=requirements,
        )
        evaluations.append(evaluation)
        comparisons.append(comparison)
    payload = {
        "protocol": protocol.model_dump(mode="json"),
        "detector_fingerprint": config.detector_fingerprint,
        "evaluations": [item.model_dump(mode="json") for item in evaluations],
        "controlled_comparisons": comparisons,
        "holdout_v3_accessed": False,
    }
    write_json(output_path, payload, overwrite=overwrite)
    _write_report(
        report_path,
        render_v3_report(
            tuple(evaluations),
            title="Strict-v3 Development",
            holdout_status="registered_unopened",
        ),
        overwrite=overwrite,
    )
    return tuple(evaluations)


def run_v3_validation(
    *,
    protocol: StrictV3Protocol,
    config: StrictV3Config,
    definition: SourceContractDefinition,
    requirements: AdministrativeRequirementsContract,
    output_path: Path,
    report_path: Path,
    lock_path: Path,
    overwrite: bool = False,
) -> V3Evaluation:
    validate_protocol_locks(protocol, config)
    evaluation, comparison = _evaluate_specification(
        specification=protocol.validation_dataset,
        protocol=protocol,
        config=config,
        definition=definition,
        requirements=requirements,
    )
    payload = {
        "protocol_id": protocol.protocol_id,
        "detector_fingerprint": config.detector_fingerprint,
        "evaluation": evaluation.model_dump(mode="json"),
        "controlled_comparison": comparison,
        "holdout_v3_accessed": False,
    }
    write_json(output_path, payload, overwrite=overwrite)
    _write_report(
        report_path,
        render_v3_report(
            (evaluation,),
            title="Strict-v3 Validation",
            holdout_status=(
                "eligible_but_unopened"
                if evaluation.promotion_assessment == "eligible_for_holdout"
                else "registered_unopened_validation_failed"
            ),
        ),
        overwrite=overwrite,
    )
    if evaluation.promotion_assessment == "eligible_for_holdout":
        lock_after_validation(
            protocol=protocol,
            config=config,
            validation=evaluation,
            path=lock_path,
        )
    return evaluation


def run_v3_holdout(
    *,
    protocol: StrictV3Protocol,
    config: StrictV3Config,
    definition: SourceContractDefinition,
    requirements: AdministrativeRequirementsContract,
    lock_path: Path,
    registry_path: Path,
    output_path: Path,
    report_path: Path,
) -> V3Evaluation | None:
    if not lock_path.exists():
        raise ValueError("strict_v3_validation_failed; holdout V3 remains unopened")
    lock = StrictV3Lock.model_validate_json(lock_path.read_text(encoding="utf-8"))
    registry = begin_v3_holdout(
        protocol=protocol,
        config=config,
        lock=lock,
        registry_path=registry_path,
    )
    if registry.status == "completed":
        if not output_path.exists():
            raise ValueError("completed holdout V3 registry has no immutable result")
        return None
    evaluation, comparison = _evaluate_specification(
        specification=protocol.holdout_dataset,
        protocol=protocol,
        config=config,
        definition=definition,
        requirements=requirements,
    )
    write_json(
        output_path,
        {
            "evaluation": evaluation.model_dump(mode="json"),
            "controlled_comparison": comparison,
        },
        overwrite=False,
    )
    complete_v3_holdout(registry, evaluation, registry_path=registry_path)
    _write_report(
        report_path,
        render_v3_report((evaluation,), title="Strict-v3 Holdout", holdout_status="completed_once"),
        overwrite=False,
    )
    return evaluation


def _write_report(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_existing_evaluation(path: Path) -> V3Evaluation:
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get("evaluation", payload)
    return V3Evaluation.model_validate(value)
