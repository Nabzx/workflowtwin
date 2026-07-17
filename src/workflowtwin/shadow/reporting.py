"""Safe machine-readable and stakeholder-readable shadow artefacts."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from workflowtwin.shadow.intake import write_jsonl
from workflowtwin.shadow.models import (
    AuditRecord,
    Recommendation,
    ReviewDecision,
    ShadowEvaluation,
    ShadowRun,
)
from workflowtwin.synthetic.artifacts import ArtifactExistsError

_RECOMMENDATIONS = TypeAdapter(tuple[Recommendation, ...])
_AUDIT = TypeAdapter(tuple[AuditRecord, ...])


def _write_text(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ArtifactExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_json(path: Path, value: BaseModel | dict[str, Any], *, overwrite: bool = False) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n", overwrite=overwrite)


def load_run(path: Path) -> ShadowRun:
    return ShadowRun.model_validate_json(path.read_text(encoding="utf-8"))


def load_recommendations(path: Path) -> tuple[Recommendation, ...]:
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return _RECOMMENDATIONS.validate_python(values)


def load_audit(path: Path) -> tuple[AuditRecord, ...]:
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return _AUDIT.validate_python(values)


def write_run_artifacts(
    run: ShadowRun,
    *,
    run_output: Path,
    recommendations_output: Path,
    audit_output: Path,
    checkpoint_output: Path | None,
    overwrite: bool,
) -> None:
    write_json(run_output, run, overwrite=overwrite)
    write_jsonl(recommendations_output, run.recommendations, overwrite=overwrite)
    write_jsonl(audit_output, run.audit_records, overwrite=overwrite)
    if checkpoint_output is not None:
        write_json(checkpoint_output, run.checkpoint, overwrite=overwrite)


def visualisation_data(evaluation: ShadowEvaluation) -> dict[str, Any]:
    return {
        "profile_comparison": evaluation.profile_comparison,
        "lifecycle_counts": {
            "recommendations": evaluation.run_manifest.recommendations,
            "revisions": evaluation.run_manifest.revisions,
            "retractions": evaluation.run_manifest.retractions,
            "expiries": evaluation.run_manifest.expiries,
            "duplicates_suppressed": evaluation.run_manifest.duplicate_suppressions,
        },
        "latency_distributions": {
            "source_to_recommendation": evaluation.source_to_recommendation_latency.model_dump(
                mode="json"
            ),
            "recommendation_to_review": evaluation.recommendation_to_review_latency.model_dump(
                mode="json"
            ),
        },
        "reviewer_decisions": evaluation.reviewer.model_dump(mode="json"),
        "policy_results": evaluation.policy.model_dump(mode="json"),
        "stop_condition_timeline": [
            item.model_dump(mode="json") for item in evaluation.stop_conditions
        ],
        "promotion_gate_states": [
            item.model_dump(mode="json") for item in evaluation.promotion_gates
        ],
    }


def markdown_report(evaluation: ShadowEvaluation) -> str:
    detector = evaluation.detector
    precision = detector.precision.value
    recall = detector.recall.value
    assessment = evaluation.promotion_assessment
    source_p95 = evaluation.source_to_recommendation_latency.p95_minutes
    review_p95 = evaluation.recommendation_to_review_latency.p95_minutes
    agreement = evaluation.reviewer.agreement_rate
    rejection = evaluation.reviewer.rejection_rate
    profile_rows = (
        "\n".join(
            f"| {item.get('profile')} | {item.get('recommendations')} | "
            f"{item.get('precision')} | {item.get('recall')} | {item.get('false_positive_hours')} |"
            for item in evaluation.profile_comparison
        )
        or "| current profile only | - | - | - | - |"
    )
    gate_rows = "\n".join(
        f"| {gate.category} | {gate.gate_id} | {gate.status.value} |"
        for gate in evaluation.promotion_gates
    )
    breached = [item.condition_id for item in evaluation.stop_conditions if item.breached]
    return f"""# WorkflowTwin recommendation shadow-mode report

## Executive summary

This report evaluates a **recommendation-only** administrative completeness detector against
replayed, fictional Northstar Clinics intake data. It does not change a workflow, communicate with
any person, provide clinical conclusions, or authorise production deployment. The deterministic
promotion assessment is **{assessment.result.replace("_", " ")}**.

Shadow mode was required because counterfactual simulation showed that false-positive review and
fallback burden could outweigh reduced manual work. The narrower detector therefore favours explicit
structured evidence, high precision, and abstention.

## Evidence chain

```text
Structured data available as of time T
→ Deterministic detector evaluation
→ Recommendation-only output
→ Human reviewer decision
→ Hidden-label evaluation after the fact
→ Safety, burden and quality gates
→ Pilot-readiness decision
```

## Online boundary and rules

Inputs are versioned administrative intake snapshots ordered by source availability, source-system
priority, and stable snapshot ID. The detector can inspect form version and presence flags
for the referral form, supporting document, source acknowledgement, and contact route. It cannot
inspect future events, eventual outcomes, hidden labels, clinical fields, free text, protected
attributes, or reviewer decisions. GP-practice membership alone never triggers a recommendation.

Strict mode recommends review for an explicitly absent required supporting document or source
acknowledgement. Unknown or unsupported required inputs cause abstention. A later structured
correction can retract a recommendation; historical lifecycle and audit records remain append-only.

## Detector quality

- Incoming cases: {detector.incoming_cases}
- Recommendations: {detector.recommendations}
- Recommendation coverage: {detector.recommendation_coverage.value}
- Abstentions: {detector.abstentions} ({detector.abstention_rate.value})
- True positives: {detector.true_positives}
- False positives: {detector.false_positives}
- False negatives: {detector.false_negatives}
- Precision: {precision}
- Recall: {recall}
- False-positive rate: {detector.false_positive_rate.value}
- Evaluation coverage: {detector.evaluation_coverage.value}

Unavailable metrics remain `null` in JSON rather than receiving a misleading zero.

## Burden, latency, and reviewers

- All fictional review hours: {evaluation.burden.all_review_hours:.3f}
- False-positive review hours: {evaluation.burden.false_positive_review_hours:.3f}
- False-positive burden per 100 cases: {evaluation.burden.false_positive_per_100_cases:.3f}
- Source-to-recommendation P95 logical minutes: {source_p95}
- Recommendation-to-review P95 logical minutes: {review_p95}
- Reviewer agreement / rejection: {agreement} / {rejection}
- Usefulness classifications: {evaluation.reviewer.usefulness_counts}

These hours and the associated GBP value are fictional capacity proxies, not realised savings.

## Profile comparison

| Profile | Recommendations | Precision | Recall | False-positive hours |
| --- | ---: | ---: | ---: | ---: |
{profile_rows}

The exploratory profile is offline evaluation-only. The default policy is strict.

## Audit and policy

- Audit records: {evaluation.audit.total_records}
- Audit completeness: {evaluation.audit.audit_completeness_rate}
- Audit chain valid: {evaluation.audit.chain_valid}
- Audit root: `{evaluation.run_manifest.audit_root_fingerprint}`
- Policy compliance: {evaluation.policy.compliance_rate}
- Policy violations: {evaluation.policy.total_policy_violations}

The hash chain is tamper-evident, not tamper-proof against a privileged file-system owner.

## Stop conditions and promotion gates

Breached stop conditions: {breached or "none"}

| Category | Gate | Status |
| --- | --- | --- |
{gate_rows}

The assessment **{assessment.result.replace("_", " ")}** means only that the configured fictional
shadow evidence was evaluated. Even a passed result would allow, at most, design of a reversible,
human-approved fictional pilot; it is not autonomous-action or production approval.

## Time-window observations

{json.dumps(evaluation.time_windows, indent=2, default=str)}

These are observed replay period differences, not formal drift claims.

## Limitations and later-pilot requirements

All cases, reviewers, labels, timings, and outcomes are synthetic. Snapshot ambiguity and reviewer
behaviour are designed assumptions. No real operational benefit, saving, clinical outcome, or ROI
has been measured. A later pilot requires every mandatory safety, policy, audit, detector-quality,
burden, and reliability gate to pass, plus explicit human approval and reversible action,
idempotency, and independent governance review.

Evaluation fingerprint: `{evaluation.evaluation_fingerprint}`
"""


def write_evaluation_artifacts(
    evaluation: ShadowEvaluation,
    *,
    evaluation_output: Path,
    report_output: Path,
    visualisation_output: Path,
    overwrite: bool,
) -> None:
    write_json(evaluation_output, evaluation, overwrite=overwrite)
    _write_text(report_output, markdown_report(evaluation), overwrite=overwrite)
    write_json(visualisation_output, visualisation_data(evaluation), overwrite=overwrite)


def write_reviews(path: Path, reviews: tuple[ReviewDecision, ...], *, overwrite: bool) -> None:
    write_jsonl(path, reviews, overwrite=overwrite)
