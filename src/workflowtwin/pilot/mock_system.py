"""Local-only adapter for the fictional Northstar administrative task system."""

from datetime import datetime

from workflowtwin.core.fingerprint import stable_id
from workflowtwin.pilot.models import (
    DraftMissingInformationRequest,
    MockReferralSystemRecord,
    MockTaskHistoryItem,
    MockTaskStatus,
)


class MockTaskNotFoundError(LookupError):
    """Raised when a fictional task identifier is unknown."""


class InMemoryMockReferralSystem:
    """Store fictional tasks without external calls or operational-event writes."""

    def __init__(self) -> None:
        self._records: dict[str, MockReferralSystemRecord] = {}
        self._idempotency_index: dict[str, str] = {}

    def create_task(
        self,
        *,
        draft: DraftMissingInformationRequest,
        idempotency_key: str,
        actor_role: str,
        occurred_at: datetime,
    ) -> tuple[MockReferralSystemRecord, bool]:
        existing_id = self._idempotency_index.get(idempotency_key)
        if existing_id is not None:
            return self._records[existing_id], False
        revision = next(
            item for item in draft.revisions if item.revision_id == draft.current_revision_id
        )
        task_id = stable_id("mock-admin-task", idempotency_key)
        history = self._history_item(
            task_id=task_id,
            index=1,
            occurred_at=occurred_at,
            actor_role=actor_role,
            action="created_after_human_approval",
            reason="approved_missing_information_draft",
            previous_status=None,
            new_status=MockTaskStatus.READY_FOR_MANUAL_SENDING,
        )
        record = MockReferralSystemRecord(
            task_id=task_id,
            idempotency_key=idempotency_key,
            case_id=draft.case_id,
            draft_id=draft.draft_id,
            revision_id=draft.current_revision_id,
            status=MockTaskStatus.READY_FOR_MANUAL_SENDING,
            heading=revision.heading,
            body=revision.body,
            item_ids=tuple(item.field_id for item in revision.items),
            created_at=occurred_at,
            updated_at=occurred_at,
            history=(history,),
        )
        self._records[task_id] = record
        self._idempotency_index[idempotency_key] = task_id
        return record, True

    def read_task(self, task_id: str) -> MockReferralSystemRecord:
        try:
            return self._records[task_id]
        except KeyError as error:
            raise MockTaskNotFoundError(f"unknown mock task: {task_id}") from error

    def cancel_task(
        self, task_id: str, *, actor_role: str, reason: str, occurred_at: datetime
    ) -> MockReferralSystemRecord:
        return self._transition(
            task_id,
            new_status=MockTaskStatus.CANCELLED,
            actor_role=actor_role,
            reason=reason,
            occurred_at=occurred_at,
            action="cancelled",
        )

    def update_approved_draft(
        self,
        task_id: str,
        *,
        draft: DraftMissingInformationRequest,
        actor_role: str,
        reason: str,
        occurred_at: datetime,
    ) -> MockReferralSystemRecord:
        current = self.read_task(task_id)
        revision = next(
            item for item in draft.revisions if item.revision_id == draft.current_revision_id
        )
        history = self._history_item(
            task_id=task_id,
            index=len(current.history) + 1,
            occurred_at=occurred_at,
            actor_role=actor_role,
            action="approved_draft_updated",
            reason=reason,
            previous_status=current.status,
            new_status=current.status,
        )
        updated = current.model_copy(
            update={
                "revision_id": draft.current_revision_id,
                "heading": revision.heading,
                "body": revision.body,
                "item_ids": tuple(item.field_id for item in revision.items),
                "updated_at": occurred_at,
                "history": (*current.history, history),
            }
        )
        self._records[task_id] = updated
        return updated

    def mark_ready_for_manual_sending(
        self, task_id: str, *, actor_role: str, reason: str, occurred_at: datetime
    ) -> MockReferralSystemRecord:
        return self._transition(
            task_id,
            new_status=MockTaskStatus.READY_FOR_MANUAL_SENDING,
            actor_role=actor_role,
            reason=reason,
            occurred_at=occurred_at,
            action="marked_ready_for_manual_sending",
        )

    def rollback_task(
        self, task_id: str, *, actor_role: str, reason: str, occurred_at: datetime
    ) -> tuple[MockReferralSystemRecord, bool]:
        current = self.read_task(task_id)
        if current.status is MockTaskStatus.ROLLED_BACK:
            return current, False
        return (
            self._transition(
                task_id,
                new_status=MockTaskStatus.ROLLED_BACK,
                actor_role=actor_role,
                reason=reason,
                occurred_at=occurred_at,
                action="rolled_back",
            ),
            True,
        )

    def list_tasks(self) -> tuple[MockReferralSystemRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def list_task_history(self, task_id: str) -> tuple[MockTaskHistoryItem, ...]:
        return self.read_task(task_id).history

    def _transition(
        self,
        task_id: str,
        *,
        new_status: MockTaskStatus,
        actor_role: str,
        reason: str,
        occurred_at: datetime,
        action: str,
    ) -> MockReferralSystemRecord:
        current = self.read_task(task_id)
        history = self._history_item(
            task_id=task_id,
            index=len(current.history) + 1,
            occurred_at=occurred_at,
            actor_role=actor_role,
            action=action,
            reason=reason,
            previous_status=current.status,
            new_status=new_status,
        )
        updated = current.model_copy(
            update={
                "status": new_status,
                "updated_at": occurred_at,
                "history": (*current.history, history),
            }
        )
        self._records[task_id] = updated
        return updated

    @staticmethod
    def _history_item(
        *,
        task_id: str,
        index: int,
        occurred_at: datetime,
        actor_role: str,
        action: str,
        reason: str,
        previous_status: MockTaskStatus | None,
        new_status: MockTaskStatus,
    ) -> MockTaskHistoryItem:
        return MockTaskHistoryItem(
            history_id=stable_id("mock-task-history", task_id, index, action),
            occurred_at=occurred_at,
            actor_role=actor_role,
            action=action,
            reason=reason,
            previous_status=previous_status,
            new_status=new_status,
        )
