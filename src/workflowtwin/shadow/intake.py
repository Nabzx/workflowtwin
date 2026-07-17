"""Deterministic fictional intake snapshots and isolated evaluation labels."""

import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from random import Random

from pydantic import TypeAdapter

from workflowtwin.domain.referrals.enums import EventType, SourceSystem
from workflowtwin.shadow.fingerprint import shadow_fingerprint, shadow_id
from workflowtwin.shadow.models import (
    FieldAvailability,
    IncomingReferralSnapshot,
    ShadowEvaluationLabel,
    ShadowLabelStatus,
)
from workflowtwin.synthetic.artifacts import ArtifactExistsError
from workflowtwin.synthetic.models import GeneratedDataset

_SNAPSHOTS = TypeAdapter(tuple[IncomingReferralSnapshot, ...])
_LABELS = TypeAdapter(tuple[ShadowEvaluationLabel, ...])


def _case_random(seed: int, case_id: object) -> Random:
    digest = shadow_fingerprint({"seed": seed, "case_id": str(case_id), "purpose": "intake-v1"})
    return Random(int(digest[:16], 16))


def generate_intake_artifacts(
    dataset: GeneratedDataset,
) -> tuple[tuple[IncomingReferralSnapshot, ...], tuple[ShadowEvaluationLabel, ...]]:
    """Derive a separate ambiguous intake stream without changing operational records."""
    events_by_case = defaultdict(list)
    for event in dataset.events:
        events_by_case[event.referral_case_id].append(event)
    truth_by_case = {truth.case_id: truth for truth in dataset.ground_truth.cases}
    snapshots: list[IncomingReferralSnapshot] = []
    labels: list[ShadowEvaluationLabel] = []

    for case in dataset.cases:
        rng = _case_random(dataset.config.seed, case.id)
        events = sorted(events_by_case[case.id], key=lambda item: (item.ingested_at, item.id.hex))
        received = next(
            event for event in events if event.event_type is EventType.REFERRAL_RECEIVED
        )
        submitted = next(
            event for event in events if event.event_type is EventType.REFERRAL_SUBMITTED
        )
        first_check = next(
            event for event in events if event.event_type is EventType.COMPLETENESS_CHECK_COMPLETED
        )
        truth = truth_by_case[case.id]
        genuinely_incomplete = "incomplete" in truth.intended_path
        form_version = rng.choices(("NS-INTAKE-2", "NS-INTAKE-1", "UNKNOWN"), (0.88, 0.08, 0.04))[0]
        ambiguous = rng.random() < 0.08
        misleading_absence = not genuinely_incomplete and rng.random() < 0.025
        explicit_absence = genuinely_incomplete and rng.random() < 0.78
        supporting_document = (
            FieldAvailability.UNKNOWN
            if ambiguous
            else FieldAvailability.ABSENT
            if explicit_absence or misleading_absence
            else FieldAvailability.PRESENT
        )
        acknowledgement = (
            FieldAvailability.UNKNOWN if rng.random() < 0.03 else FieldAvailability.PRESENT
        )
        contact_route = (
            FieldAvailability.ABSENT if rng.random() < 0.04 else FieldAvailability.PRESENT
        )
        available_at = max(received.ingested_at, submitted.ingested_at)
        source_system = submitted.source_system
        if source_system is SourceSystem.SYNTHETIC_GENERATOR:
            source_system = SourceSystem.REFERRAL_PORTAL
        first = IncomingReferralSnapshot(
            snapshot_id=shadow_id("snapshot", dataset.manifest.generation_run_id, case.id, 1),
            case_id=case.id,
            available_at=available_at,
            source_event_id=received.id,
            source_system=source_system,
            referral_source=case.referral_source,
            requested_service_line=case.service_line,
            submitting_organisation_id=shadow_id("org", case.referral_source.value, length=10),
            form_version=form_version,
            source_record_version=1,
            referral_form=FieldAvailability.PRESENT,
            supporting_document=supporting_document,
            source_acknowledgement=acknowledgement,
            contact_route=contact_route,
        )
        snapshots.append(first)

        correction_at = None
        if (
            supporting_document in {FieldAvailability.ABSENT, FieldAvailability.UNKNOWN}
            and rng.random() < 0.28
        ):
            delay = timedelta(minutes=rng.uniform(8, 180))
            correction_at = min(
                available_at + delay, first_check.ingested_at + timedelta(minutes=5)
            )
            second = first.model_copy(
                update={
                    "snapshot_id": shadow_id(
                        "snapshot", dataset.manifest.generation_run_id, case.id, 2
                    ),
                    "available_at": correction_at,
                    "source_event_id": None,
                    "source_record_version": 2,
                    "supporting_document": FieldAvailability.PRESENT,
                }
            )
            snapshots.append(second)
            if rng.random() < 0.12:
                snapshots.append(second.model_copy(update={"is_source_retry": True}))

        label_status = (
            ShadowLabelStatus.POSITIVE if genuinely_incomplete else ShadowLabelStatus.NEGATIVE
        )
        labels.append(
            ShadowEvaluationLabel(
                label_id=shadow_id("label", dataset.manifest.generation_run_id, case.id, 1),
                case_id=case.id,
                valid_from=available_at,
                valid_until=correction_at if genuinely_incomplete and correction_at else None,
                status=label_status,
                evidence_codes=("synthetic_intake_truth",),
            )
        )
        if genuinely_incomplete and correction_at:
            labels.append(
                ShadowEvaluationLabel(
                    label_id=shadow_id("label", dataset.manifest.generation_run_id, case.id, 2),
                    case_id=case.id,
                    valid_from=correction_at,
                    status=ShadowLabelStatus.NEGATIVE,
                    evidence_codes=("administrative_field_corrected",),
                )
            )

    ordered_snapshots = tuple(
        sorted(snapshots, key=lambda item: (item.available_at, item.snapshot_id))
    )
    ordered_labels = tuple(sorted(labels, key=lambda item: (item.valid_from, item.label_id)))
    return ordered_snapshots, ordered_labels


def intake_snapshot_fingerprint(snapshots: tuple[IncomingReferralSnapshot, ...]) -> str:
    return shadow_fingerprint([item.model_dump(mode="json") for item in snapshots])


def write_jsonl(path: Path, records: tuple[object, ...], *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise ArtifactExistsError(f"artifact already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    lines = []
    for record in records:
        if not hasattr(record, "model_dump"):
            raise TypeError("JSONL records must be Pydantic models")
        lines.append(json.dumps(record.model_dump(mode="json"), sort_keys=True))
    temporary.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    temporary.replace(path)


def _load_jsonl(path: Path) -> list[object]:
    values: list[object] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            values.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at {path}:{line_number}") from error
    return values


def load_intake_snapshots(path: Path) -> tuple[IncomingReferralSnapshot, ...]:
    return _SNAPSHOTS.validate_python(_load_jsonl(path))


def load_evaluation_labels(path: Path) -> tuple[ShadowEvaluationLabel, ...]:
    return _LABELS.validate_python(_load_jsonl(path))
