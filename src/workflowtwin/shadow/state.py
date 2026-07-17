"""Incremental as-of-time projection for fictional intake snapshots."""

from dataclasses import dataclass, field

from workflowtwin.shadow.models import (
    AdministrativeFieldState,
    IncomingReferralSnapshot,
    ShadowCaseState,
)


@dataclass(slots=True)
class CaseStateProjector:
    """Apply source versions while retaining immutable state revisions."""

    current: dict[object, ShadowCaseState] = field(default_factory=dict)
    revisions: dict[object, list[ShadowCaseState]] = field(default_factory=dict)
    seen_snapshot_ids: set[str] = field(default_factory=set)

    def apply(self, snapshot: IncomingReferralSnapshot) -> tuple[ShadowCaseState | None, str]:
        if snapshot.snapshot_id in self.seen_snapshot_ids:
            existing = self.current.get(snapshot.case_id)
            if existing is not None:
                updated = existing.model_copy(
                    update={"duplicate_update_count": existing.duplicate_update_count + 1}
                )
                self.current[snapshot.case_id] = updated
            return None, "duplicate_source_item"
        self.seen_snapshot_ids.add(snapshot.snapshot_id)
        previous = self.current.get(snapshot.case_id)
        if previous and snapshot.source_record_version < previous.source_record_version:
            updated = previous.model_copy(
                update={
                    "stale_update_count": previous.stale_update_count + 1,
                    "warnings": tuple(sorted({*previous.warnings, "stale_source_update"})),
                }
            )
            self.current[snapshot.case_id] = updated
            return None, "stale_source_item"
        state = ShadowCaseState(
            case_id=snapshot.case_id,
            state_version=(previous.state_version + 1 if previous else 1),
            as_of=snapshot.available_at,
            referral_source=snapshot.referral_source,
            requested_service_line=snapshot.requested_service_line,
            source_system=snapshot.source_system,
            form_version=snapshot.form_version,
            source_record_version=snapshot.source_record_version,
            fields=AdministrativeFieldState(
                referral_form=snapshot.referral_form,
                supporting_document=snapshot.supporting_document,
                source_acknowledgement=snapshot.source_acknowledgement,
                contact_route=snapshot.contact_route,
            ),
            source_snapshot_ids=(
                (*previous.source_snapshot_ids, snapshot.snapshot_id)
                if previous
                else (snapshot.snapshot_id,)
            ),
            stale_update_count=previous.stale_update_count if previous else 0,
            duplicate_update_count=previous.duplicate_update_count if previous else 0,
            warnings=previous.warnings if previous else (),
        )
        if snapshot.available_at > state.as_of:
            raise AssertionError("source snapshot cannot exceed the projection cutoff")
        self.current[snapshot.case_id] = state
        self.revisions.setdefault(snapshot.case_id, []).append(state)
        return state, "state_updated"

    def restore(self, states: tuple[ShadowCaseState, ...]) -> None:
        for state in states:
            self.current[state.case_id] = state
            self.revisions[state.case_id] = [state]
            self.seen_snapshot_ids.update(state.source_snapshot_ids)
