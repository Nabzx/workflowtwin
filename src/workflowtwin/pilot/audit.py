"""Append-only tamper-evident audit records for fictional pilot activity."""

from datetime import datetime

from workflowtwin.core.fingerprint import fingerprint, stable_id
from workflowtwin.pilot.models import PilotAuditRecord


def append_audit(
    records: tuple[PilotAuditRecord, ...],
    *,
    occurred_at: datetime,
    actor_role: str,
    action: str,
    object_id: str,
    input_references: tuple[str, ...] = (),
    output_references: tuple[str, ...] = (),
    reason_codes: tuple[str, ...] = (),
) -> tuple[PilotAuditRecord, ...]:
    sequence = len(records) + 1
    previous = records[-1].content_fingerprint if records else None
    audit_id = stable_id("pilot-audit", sequence, action, object_id, occurred_at.isoformat())
    content = {
        "audit_id": audit_id,
        "sequence_number": sequence,
        "occurred_at": occurred_at,
        "actor_role": actor_role,
        "action": action,
        "object_id": object_id,
        "input_references": input_references,
        "output_references": output_references,
        "reason_codes": reason_codes,
        "previous_record_fingerprint": previous,
    }
    record = PilotAuditRecord.model_validate(
        {**content, "content_fingerprint": fingerprint(content)}
    )
    return (*records, record)


def verify_pilot_audit(records: tuple[PilotAuditRecord, ...]) -> tuple[bool, int]:
    previous = None
    broken = 0
    for sequence, record in enumerate(records, start=1):
        content = record.model_dump(mode="python", exclude={"content_fingerprint"})
        if (
            record.sequence_number != sequence
            or record.previous_record_fingerprint != previous
            or fingerprint(content) != record.content_fingerprint
        ):
            broken += 1
        previous = record.content_fingerprint
    return broken == 0, broken
