"""Atomic machine-readable and concise stakeholder refinement reports."""

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, value: Any, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def render_markdown(results: list[dict[str, object]], *, title: str) -> str:
    lines = [
        f"# {title}",
        "",
        "> All organisations, cases, reviews, capacity assumptions, and results are fictional.",
        "> Administrative recommendation-only shadow analysis; no workflow action is taken.",
        "",
        "| Split | Version | Positives | Precision | Recall | FP hours | Mean latency |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        dataset = result["dataset"]
        assert isinstance(dataset, dict)
        for key in ("strict_v1", "strict_v2"):
            evaluation = result[key]
            assert isinstance(evaluation, dict)
            detector = evaluation["detector"]
            assert isinstance(detector, dict)
            lines.append(
                "| {split} | {version} | {positives} | {precision:.3f} | {recall:.3f} | "
                "{hours:.3f} | {latency:.1f} min |".format(
                    split=dataset["dataset_id"],
                    version=key.replace("_", "-"),
                    positives=detector["detector_positives"],
                    precision=detector["precision"] or 0,
                    recall=detector["recall"] or 0,
                    hours=detector["false_positive_review_hours"],
                    latency=detector["recommendation_latency_mean_minutes"] or 0,
                )
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Capacity results only describe which detector positives could be surfaced under "
            "fictional reviewer assumptions. They cannot alter detector quality.",
            "",
            "Promotion remains a separate governance decision. No result authorises automation, "
            "patient contact, referral handling, diagnosis, or treatment advice.",
        ]
    )
    return "\n".join(lines) + "\n"
