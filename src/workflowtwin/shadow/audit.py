"""Append-only tamper-evident audit chaining."""

from datetime import datetime
from uuid import UUID

from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.fingerprint import shadow_fingerprint, shadow_id
from workflowtwin.shadow.models import AuditActor, AuditRecord


class AuditTrail:
    def __init__(self, config: ShadowConfig, records: tuple[AuditRecord, ...] = ()) -> None:
        self.config = config
        self.records = list(records)

    @property
    def root_fingerprint(self) -> str | None:
        return self.records[-1].content_fingerprint if self.records else None

    def append(
        self,
        *,
        occurred_at: datetime,
        actor: AuditActor,
        action: str,
        case_id: UUID | None = None,
        recommendation_id: str | None = None,
        reason_codes: tuple[str, ...] = (),
        input_references: tuple[str, ...] = (),
        output_references: tuple[str, ...] = (),
    ) -> AuditRecord:
        sequence = len(self.records) + 1
        previous = self.root_fingerprint
        audit_id = shadow_id("audit", self.config.shadow_run_id, sequence, action)
        content = {
            "audit_id": audit_id,
            "shadow_run_id": self.config.shadow_run_id,
            "sequence_number": sequence,
            "occurred_at": occurred_at,
            "case_id": case_id,
            "recommendation_id": recommendation_id,
            "actor": actor,
            "action": action,
            "reason_codes": reason_codes,
            "input_references": input_references,
            "output_references": output_references,
            "detector_version": self.config.detector_version,
            "policy_version": self.config.policy_version,
            "previous_record_fingerprint": previous,
        }
        record = AuditRecord.model_validate(
            {**content, "content_fingerprint": shadow_fingerprint(content)}
        )
        self.records.append(record)
        return record


def verify_audit_chain(records: tuple[AuditRecord, ...]) -> tuple[bool, int]:
    previous: str | None = None
    broken = 0
    for expected_sequence, record in enumerate(records, start=1):
        content = record.model_dump(mode="python", exclude={"content_fingerprint"})
        if (
            record.sequence_number != expected_sequence
            or record.previous_record_fingerprint != previous
            or shadow_fingerprint(content) != record.content_fingerprint
        ):
            broken += 1
        previous = record.content_fingerprint
    return broken == 0, broken
