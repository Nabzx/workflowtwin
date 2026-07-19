"""Small deterministic JSON and Markdown pilot evidence artifacts."""

import json
from pathlib import Path

from workflowtwin.pilot.models import PilotRun


def render_pilot_report(run: PilotRun) -> str:
    passed = sum(item.status == "pass" for item in run.gates)
    example = run.drafts[0].revisions[-1]
    return f"""# Northstar Fictional Pilot Report

Northstar Clinics, the cohort, and every result in this report are fictional.

## Decision context

- Selected opportunity: administrative referral completeness review
- Supported detector: `{run.supported_detector_metadata["product_name"]}`
- Lineage: derived from `{run.supported_detector_metadata["derived_from"]}`
- Original strict-v3 result: `strict_v3_validation_failed`
- Pilot assessment: `{run.assessment.value}`

Strict-v3 failed its original pre-registered detector-positive coverage gate. This separate
pilot policy does not rewrite that result: it limits capacity using surfaced recommendations,
completed reviews, review minutes, queue depth, and latency while still reporting raw
detector-positive coverage.

## Human control

Every task requires a permitted fictional reviewer to approve the current draft revision.
Reviewers may edit, approve, reject, cancel, mark unnecessary, or request more context.
There is no sending endpoint, automatic rejection, routing, service-line change, or clinical
inference. Committed tasks exist only in a local mock adapter and remain reversible.

### Draft example

```text
{example.heading}

{example.body}
```

## Evidence

| Measure | Result |
|---|---:|
| Incoming fictional cases | {run.metrics.incoming_cases} |
| Detector-positive coverage | {run.metrics.detector_positive_coverage:.1%} |
| Surfaced recommendation coverage | {run.metrics.surfaced_recommendation_coverage:.1%} |
| Precision | {run.metrics.detector_precision:.1%} |
| Recall | {run.metrics.detector_recall:.1%} |
| Review minutes | {run.metrics.review_minutes:.1f} |
| Maximum queue depth | {run.metrics.maximum_queue_depth} |
| Fictional tasks committed | {run.metrics.fictional_tasks_committed} |
| Rollbacks | {run.metrics.rollbacks} |
| Policy gates passed | {passed}/{len(run.gates)} |

## Stop conditions

{", ".join(run.stop_conditions) if run.stop_conditions else "None triggered."}

## Limitations

This deterministic local demonstration is not production approval, a clinical system, or
evidence of real outcomes, staff time saved, cost reduction, or ROI. No message was sent and
no operational referral record was changed.
"""


def write_pilot_artifacts(
    run: PilotRun, output_dir: Path, *, overwrite: bool = False
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "pilot-run.json"
    report_path = output_dir / "pilot-report.md"
    if not overwrite and (json_path.exists() or report_path.exists()):
        raise FileExistsError("pilot artifacts already exist; use --reset to replace them")
    json_path.write_text(
        json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(render_pilot_report(run), encoding="utf-8")
    return json_path, report_path
