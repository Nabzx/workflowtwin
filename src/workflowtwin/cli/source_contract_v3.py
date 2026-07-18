"""CLI commands for source-contract diagnostics and strict-v3 gated evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from workflowtwin.services.shadow_v3 import (
    run_v3_development,
    run_v3_holdout,
    run_v3_validation,
)
from workflowtwin.services.source_contract_analysis import (
    analyse_historical_source_contract,
    render_historical_analysis,
)
from workflowtwin.shadow.fingerprint import shadow_fingerprint
from workflowtwin.shadow_refinement.protocol import load_refinement_protocol
from workflowtwin.shadow_v3.config import StrictV3Config
from workflowtwin.shadow_v3.models import StrictV3Protocol
from workflowtwin.shadow_v3.protocol import load_v3_protocol
from workflowtwin.source_contracts.generator import generate_v2_intake_artifacts
from workflowtwin.source_contracts.io import (
    load_requirements,
    load_source_contract,
    write_json,
    write_v2_jsonl,
)
from workflowtwin.source_contracts.models import SourceContractDefinition
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.states import FIELD_STATE_SEMANTICS
from workflowtwin.source_contracts.validation import validate_definition, validate_snapshots
from workflowtwin.synthetic.artifacts import load_dataset

SOURCE_CONTRACT = Path("config/shadow/source-contract-v2.json")
REQUIREMENTS = Path("config/shadow/northstar-requirements-v2.json")
V3_PROTOCOL = Path("config/shadow/strict-v3-protocol.json")
OLD_PROTOCOL = Path("config/shadow/refinement-protocol.json")
SOURCE_ARTIFACTS = Path("artifacts/source-contract")
V3_ARTIFACTS = Path("artifacts/shadow-v3")


def _contract_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-contract", type=Path, default=SOURCE_CONTRACT)
    parser.add_argument("--requirements", type=Path, default=REQUIREMENTS)


def _v3_arguments(parser: argparse.ArgumentParser) -> None:
    _contract_arguments(parser)
    parser.add_argument("--protocol", type=Path, default=V3_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, default=V3_ARTIFACTS)


def configure_source_contract_v3_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    analyse = subparsers.add_parser(
        "shadow-analyse-misses", help="classify prior misses and estimate V2 observability"
    )
    _contract_arguments(analyse)
    analyse.add_argument("--protocol", type=Path, default=OLD_PROTOCOL)
    analyse.add_argument(
        "--analysis-output",
        type=Path,
        default=SOURCE_ARTIFACTS / "missed-positive-analysis.json",
    )
    analyse.add_argument(
        "--report-output",
        type=Path,
        default=SOURCE_ARTIFACTS / "missed-positive-analysis.md",
    )
    analyse.add_argument("--force", action="store_true")

    validate = subparsers.add_parser(
        "source-contract-validate", help="validate V2 source and requirements definitions"
    )
    _contract_arguments(validate)
    validate.add_argument(
        "--validation-output",
        type=Path,
        default=SOURCE_ARTIFACTS / "validation.json",
    )
    validate.add_argument("--force", action="store_true")

    build = subparsers.add_parser(
        "source-contract-build", help="project a synthetic dataset into V2 source artifacts"
    )
    _contract_arguments(build)
    build.add_argument("--dataset", type=Path, required=True)
    build.add_argument("--snapshots-output", type=Path, required=True)
    build.add_argument("--truth-output", type=Path, required=True)
    build.add_argument("--validation-output", type=Path, required=True)
    build.add_argument("--force", action="store_true")

    develop = subparsers.add_parser(
        "shadow-v3-develop", help="evaluate registered development C and D"
    )
    _v3_arguments(develop)
    develop.add_argument("--force", action="store_true")

    validation = subparsers.add_parser(
        "shadow-v3-validate", help="evaluate validation V3 and lock only on pass"
    )
    _v3_arguments(validation)
    validation.add_argument("--force", action="store_true")

    holdout = subparsers.add_parser(
        "shadow-v3-holdout", help="evaluate registered holdout once after a valid lock"
    )
    _v3_arguments(holdout)


def run_shadow_analyse_misses(args: argparse.Namespace) -> int:
    protocol = load_refinement_protocol(args.protocol)
    definition = load_source_contract(args.source_contract)
    requirements = load_requirements(args.requirements)
    payload = analyse_historical_source_contract(
        protocol=protocol,
        definition=definition,
        requirements=requirements,
    )
    write_json(args.analysis_output, payload, overwrite=args.force)
    _write_text(
        args.report_output,
        render_historical_analysis(payload),
        overwrite=args.force,
    )
    print(f"Source-contract analysis: {args.analysis_output}")
    print("Recommendations generated: 0")
    return 0


def run_source_contract_validate(args: argparse.Namespace) -> int:
    definition = load_source_contract(args.source_contract)
    requirements = load_requirements(args.requirements)
    validate_definition(definition, requirements)
    payload = {
        "valid": True,
        "source_contract_version": definition.contract_version,
        "source_contract_fingerprint": shadow_fingerprint(definition),
        "requirements_contract_version": requirements.contract_version,
        "requirements_contract_fingerprint": shadow_fingerprint(requirements),
        "field_state_semantics": {
            state.value: semantics.model_dump(mode="json")
            for state, semantics in FIELD_STATE_SEMANTICS.items()
        },
        "clinical_fields_permitted": False,
        "recommendation_only": True,
    }
    write_json(args.validation_output, payload, overwrite=args.force)
    print(f"Validated source and requirements contracts: {args.validation_output}")
    return 0


def run_source_contract_build(args: argparse.Namespace) -> int:
    dataset = load_dataset(args.dataset)
    definition = load_source_contract(args.source_contract)
    requirements = load_requirements(args.requirements)
    snapshots, truth = generate_v2_intake_artifacts(dataset, requirements)
    validation = validate_snapshots(
        snapshots, definition=definition, requirements=requirements
    )
    write_v2_jsonl(args.snapshots_output, snapshots, overwrite=args.force)
    write_json(
        args.truth_output,
        {
            "fictional": True,
            "detector_access_permitted": False,
            "records": [item.model_dump(mode="json") for item in truth],
        },
        overwrite=args.force,
    )
    write_json(args.validation_output, validation, overwrite=args.force)
    print(f"Built {len(snapshots)} V2 snapshots from {len(dataset.cases)} fictional cases.")
    print(f"Snapshots: {args.snapshots_output}")
    print(f"Generator-only truth: {args.truth_output}")
    return 0 if validation.is_valid else 2


def _inputs(
    args: argparse.Namespace,
) -> tuple[
    StrictV3Protocol,
    StrictV3Config,
    SourceContractDefinition,
    AdministrativeRequirementsContract,
]:
    return (
        load_v3_protocol(args.protocol),
        StrictV3Config(),
        load_source_contract(args.source_contract),
        load_requirements(args.requirements),
    )


def run_shadow_v3_develop(args: argparse.Namespace) -> int:
    protocol, config, definition, requirements = _inputs(args)
    evaluations = run_v3_development(
        protocol=protocol,
        config=config,
        definition=definition,
        requirements=requirements,
        output_path=args.output_dir / "development.json",
        report_path=args.output_dir / "development.md",
        overwrite=args.force,
    )
    print(f"Evaluated {len(evaluations)} strict-v3 development splits.")
    print(f"Detector fingerprint: {config.detector_fingerprint}")
    return 0


def run_shadow_v3_validate(args: argparse.Namespace) -> int:
    protocol, config, definition, requirements = _inputs(args)
    evaluation = run_v3_validation(
        protocol=protocol,
        config=config,
        definition=definition,
        requirements=requirements,
        output_path=args.output_dir / "validation.json",
        report_path=args.output_dir / "validation.md",
        lock_path=args.output_dir / "strict-v3-lock.json",
        overwrite=args.force,
    )
    print(f"Validation assessment: {evaluation.promotion_assessment}")
    print("Holdout V3 remains unopened." if evaluation.stop_condition_breaches else "Lock created.")
    return 0 if not evaluation.stop_condition_breaches else 2


def run_shadow_v3_holdout(args: argparse.Namespace) -> int:
    protocol, config, definition, requirements = _inputs(args)
    evaluation = run_v3_holdout(
        protocol=protocol,
        config=config,
        definition=definition,
        requirements=requirements,
        lock_path=args.output_dir / "strict-v3-lock.json",
        registry_path=args.output_dir / "holdout-registry.json",
        output_path=args.output_dir / "holdout.json",
        report_path=args.output_dir / "holdout.md",
    )
    if evaluation is None:
        print("Returning immutable existing holdout V3 result.")
    else:
        print(f"Holdout V3 assessment: {evaluation.promotion_assessment}")
    return 0


def _write_text(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
