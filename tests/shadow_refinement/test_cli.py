"""End-to-end refinement CLI coverage with a small registered protocol."""

import json
from pathlib import Path

from workflowtwin.cli.main import main
from workflowtwin.shadow_refinement.models import DatasetRole, DatasetSpecification
from workflowtwin.shadow_refinement.protocol import load_refinement_protocol, write_protocol


def _spec(dataset_id: str, role: DatasetRole, seed: int, cases: int) -> DatasetSpecification:
    return DatasetSpecification(
        dataset_id=dataset_id,
        role=role,
        seed=seed,
        case_count=cases,
        operating_days=20,
        generation_run_id=f"tiny-{dataset_id}",
    )


def test_refinement_and_idempotent_holdout_cli(tmp_path: Path) -> None:
    source = load_refinement_protocol(Path("config/shadow/refinement-protocol.json"))
    protocol = source.model_copy(
        update={
            "protocol_id": "tiny-refinement-test",
            "development_datasets": (_spec("tiny-development", DatasetRole.DEVELOPMENT, 11, 30),),
            "validation_datasets": (_spec("tiny-validation", DatasetRole.VALIDATION, 12, 40),),
            "holdout_dataset": _spec("tiny-holdout", DatasetRole.HOLDOUT, 13, 50),
        }
    )
    protocol_path = tmp_path / "protocol.json"
    output = tmp_path / "results"
    write_protocol(protocol_path, protocol)
    assert (
        main(
            [
                "shadow-refine",
                "--protocol",
                str(protocol_path),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    development = json.loads((output / "development-validation.json").read_text(encoding="utf-8"))
    assert len(development["results"]) == 2
    assert len(development["sensitivity"]) == 3
    assert development["decision"].startswith("do_not_promote")

    command = [
        "shadow-holdout",
        "--protocol",
        str(protocol_path),
        "--output-dir",
        str(output),
    ]
    assert main(command) == 0
    assert main(command) == 0
    registry = json.loads((output / "holdout-registry.json").read_text(encoding="utf-8"))
    result = json.loads((output / "holdout.json").read_text(encoding="utf-8"))
    assert registry["evaluation_count"] == 1
    assert registry["status"] == "completed"
    assert result["strict_v2"]["detector"]["policy_compliance"] == 1
