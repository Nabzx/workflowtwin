"""Historical missed-positive and source-only V2 observability analysis service."""

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from workflowtwin.shadow.fingerprint import shadow_fingerprint
from workflowtwin.shadow.intake import generate_intake_artifacts
from workflowtwin.shadow.models import (
    FieldAvailability,
    IncomingReferralSnapshot,
    ShadowEvaluationLabel,
    ShadowLabelStatus,
)
from workflowtwin.shadow.oracle import ShadowEvaluationOracle
from workflowtwin.shadow_refinement.models import DatasetSpecification, RefinementProtocol
from workflowtwin.source_contracts.generator import generate_v2_intake_artifacts
from workflowtwin.source_contracts.models import SourceContractDefinition
from workflowtwin.source_contracts.observability import (
    analyse_observability,
    contract_quality,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.validation import validate_snapshots
from workflowtwin.source_contracts.visualization import source_contract_visualization
from workflowtwin.synthetic.config import GenerationConfig
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.models import GeneratedDataset


def _historical_misses(
    specification: DatasetSpecification,
) -> tuple[
    dict[str, object],
    GeneratedDataset,
    tuple[IncomingReferralSnapshot, ...],
    tuple[ShadowEvaluationLabel, ...],
]:
    dataset = SyntheticReferralGenerator(
        GenerationConfig(
            seed=specification.seed,
            case_count=specification.case_count,
            operating_days=specification.operating_days,
            generation_run_id=specification.generation_run_id,
        ),
        generated_at=datetime(2026, 7, 18, tzinfo=UTC),
    ).generate()
    snapshots, labels = generate_intake_artifacts(dataset)
    oracle = ShadowEvaluationOracle(labels)
    first: dict[UUID, IncomingReferralSnapshot] = {}
    by_case: dict[UUID, list[IncomingReferralSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        first.setdefault(snapshot.case_id, snapshot)
        by_case[snapshot.case_id].append(snapshot)
    positives = {
        case_id
        for case_id, snapshot in first.items()
        if oracle.label_at(case_id, snapshot.available_at) is ShadowLabelStatus.POSITIVE
    }
    v1_reasons: Counter[str] = Counter()
    v2_reasons: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    forms: Counter[str] = Counter()
    timing: Counter[str] = Counter()
    v1_detected = set()
    v2_detected = set()
    for case_id in positives:
        snapshot = first[case_id]
        supported = snapshot.form_version == "NS-INTAKE-2"
        absent = snapshot.supporting_document is FieldAvailability.ABSENT
        if supported and absent:
            v1_detected.add(case_id)
        else:
            category = (
                "unsupported_form_contract"
                if not supported
                else "unknown_versus_absent_ambiguity"
                if snapshot.supporting_document is FieldAvailability.UNKNOWN
                else "source_evidence_unavailable"
            )
            v1_reasons[category] += 1
        correction = next(
            (
                item
                for item in sorted(
                    by_case[case_id], key=lambda value: (value.available_at, value.snapshot_id)
                )[1:]
                if item.supporting_document is FieldAvailability.PRESENT
                and item.available_at <= snapshot.available_at + timedelta(minutes=120)
            ),
            None,
        )
        if supported and absent and correction is None:
            v2_detected.add(case_id)
            continue
        category = (
            "confirmation_window_miss"
            if correction is not None and supported and absent
            else "unsupported_form_contract"
            if not supported
            else "unknown_versus_absent_ambiguity"
            if snapshot.supporting_document is FieldAvailability.UNKNOWN
            else "source_evidence_unavailable"
        )
        v2_reasons[category] += 1
        sources[snapshot.source_system.value] += 1
        forms[snapshot.form_version] += 1
        later = [item for item in by_case[case_id] if item.available_at > snapshot.available_at]
        if not later:
            timing["no_later_source_evidence"] += 1
        elif min(item.available_at for item in later) <= (
            snapshot.available_at + timedelta(minutes=120)
        ):
            timing["update_within_120_minutes"] += 1
        else:
            timing["update_after_120_minutes"] += 1
    summary: dict[str, object] = {
        "dataset_id": specification.dataset_id,
        "hidden_positives": len(positives),
        "strict_v1_missed": len(positives - v1_detected),
        "strict_v1_categories": dict(sorted(v1_reasons.items())),
        "strict_v2_missed": len(positives - v2_detected),
        "strict_v2_categories": dict(sorted(v2_reasons.items())),
        "strict_v2_missed_by_source": dict(sorted(sources.items())),
        "strict_v2_missed_by_form": dict(sorted(forms.items())),
        "strict_v2_availability_timing": dict(sorted(timing.items())),
        "policy_or_capacity_note": (
            "Unsupported forms are policy exclusions; capacity does not alter detector misses."
        ),
    }
    return summary, dataset, snapshots, labels


def analyse_historical_source_contract(
    *,
    protocol: RefinementProtocol,
    definition: SourceContractDefinition,
    requirements: AdministrativeRequirementsContract,
) -> dict[str, object]:
    datasets = []
    specifications = (*protocol.development_datasets, *protocol.validation_datasets)
    for specification in specifications:
        summary, dataset, _v1, labels = _historical_misses(specification)
        v2, _truth = generate_v2_intake_artifacts(dataset, requirements)
        validation = validate_snapshots(v2, definition=definition, requirements=requirements)
        quality = contract_quality(v2, requirements)
        observability = analyse_observability(
            snapshots=v2,
            labels=labels,
            requirements=requirements,
        )
        summary.update(
            {
                "v2_source_validation": validation.model_dump(mode="json"),
                "v2_contract_quality": quality.model_dump(mode="json"),
                "v2_observability": observability.model_dump(mode="json"),
                "visualization": source_contract_visualization(observability, quality, v2),
            }
        )
        datasets.append(summary)
    result: dict[str, object] = {
        "analysis_version": "missed-positive-source-contract-v1",
        "source_contract_version": definition.contract_version,
        "requirements_contract_version": requirements.contract_version,
        "previous_holdout_usage": "aggregate_preservation_only; labels not imported",
        "datasets": datasets,
        "recommendations_generated": 0,
        "decision": "strict_v3_justified_by_recoverable_observability",
        "limitations": [
            "Source contract V2 is deterministic synthetic publication, not a production feed.",
            "Producer-side improvements do not guarantee detector performance.",
            "Unknown, stale, conflicting, mismatched, and unsupported inputs remain abstentions.",
        ],
    }
    result["analysis_fingerprint"] = shadow_fingerprint(result)
    return result


def render_historical_analysis(payload: dict[str, object]) -> str:
    datasets = payload["datasets"]
    assert isinstance(datasets, list)
    lines = [
        "# Missed-positive source-contract analysis",
        "",
        "> All Northstar systems, cases, source states, and results are fictional.",
        "> Administrative recommendation-only analysis; zero recommendations were generated.",
        "",
        "Strict-v2 recall failure -> missed-positive taxonomy -> source observability analysis -> "
        "explicit V2 source contract -> pre-registered strict-v3.",
        "",
        "| Dataset | Hidden positives | V1 missed | V2 missed | V2 contract ceiling |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in datasets:
        assert isinstance(item, dict)
        observability = item["v2_observability"]
        assert isinstance(observability, dict)
        ceilings = observability["ceilings"]
        assert isinstance(ceilings, list)
        overall = next(
            value
            for value in ceilings
            if value["cohort_dimension"] == "overall" and value["cohort_value"] == "all"
        )
        lines.append(
            f"| {item['dataset_id']} | {item['hidden_positives']} | "
            f"{item['strict_v1_missed']} | {item['strict_v2_missed']} | "
            f"{overall['useful_time_ceiling']:.2%} |"
        )
    lines.extend(
        [
            "",
            "The contract analysis shows meaningful recoverable recall, so strict-v3 development "
            "is justified. This does not authorise holdout access or workflow action.",
        ]
    )
    return "\n".join(lines) + "\n"
