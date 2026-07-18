"""Deterministic fictional reviewer-capacity queue for shadow recommendations."""

from collections import defaultdict
from datetime import date, datetime
from statistics import mean

from workflowtwin.shadow.fingerprint import shadow_fingerprint, shadow_id
from workflowtwin.shadow_refinement.config import ReviewerCapacityConfig
from workflowtwin.shadow_refinement.models import (
    CapacityMetrics,
    ConfirmationStatus,
    PriorityLevel,
    QueueCheckpoint,
    QueueEvent,
    QueueStatus,
    RefinedSignal,
)

_PRIORITY_RANK = {
    PriorityLevel.ADMINISTRATIVE_HIGH: 0,
    PriorityLevel.STANDARD: 1,
    PriorityLevel.LOW: 2,
}


def _percentile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * proportion)]


def apply_capacity(
    signals: tuple[RefinedSignal, ...],
    config: ReviewerCapacityConfig,
    *,
    incoming_case_count: int | None = None,
) -> tuple[tuple[QueueEvent, ...], CapacityMetrics]:
    """Surface confirmed signals by stable priority/date/id order, retaining all outcomes."""
    positive = [item for item in signals if item.status is ConfirmationStatus.CONFIRMED]
    observe = [
        item
        for item in positive
        if item.priority in {PriorityLevel.OBSERVE_ONLY, PriorityLevel.ABSTAIN}
    ]
    active = [item for item in positive if item.priority in _PRIORITY_RANK]
    by_day: dict[date, list[RefinedSignal]] = defaultdict(list)
    for signal in active:
        by_day[signal.decided_at.date()].append(signal)
    events: list[QueueEvent] = []
    sequence = 0
    queue_depth = 0
    surfaced = 0
    deferred = 0
    delays: list[float] = []

    def append(
        signal: RefinedSignal, status: QueueStatus, at: datetime, reasons: tuple[str, ...]
    ) -> None:
        nonlocal sequence
        sequence += 1
        age = max(0.0, (at - signal.decided_at).total_seconds() / 60)
        event_id = shadow_id("queue-event", config.profile, signal.signal_id, sequence, status)
        content = {
            "id": event_id,
            "signal": signal.signal_id,
            "at": at.isoformat(),
            "status": status,
            "sequence": sequence,
        }
        events.append(
            QueueEvent(
                queue_event_id=event_id,
                signal_id=signal.signal_id,
                case_id=signal.case_id,
                occurred_at=at,
                sequence_number=sequence,
                status=status,
                priority=signal.priority,
                reason_codes=reasons,
                queue_depth=queue_depth,
                queue_age_minutes=age,
                capacity_profile=config.profile,
                capacity_fingerprint=config.capacity_fingerprint,
                audit_reference=signal.audit_reference,
                content_fingerprint=shadow_fingerprint(content),
            )
        )

    for signal in observe:
        append(signal, QueueStatus.OBSERVE_ONLY, signal.decided_at, signal.priority_reasons)
    for day in sorted(by_day):
        daily = sorted(
            by_day[day],
            key=lambda item: (_PRIORITY_RANK[item.priority], item.decided_at, item.signal_id),
        )
        available = config.daily_review_slots if day.weekday() < 5 or config.weekends_enabled else 0
        for index, signal in enumerate(daily):
            queue_depth += 1
            append(signal, QueueStatus.QUEUED, signal.decided_at, ("capacity_queue_entry",))
            if index < available and queue_depth <= config.maximum_active_queue_size:
                queue_depth -= 1
                surfaced += 1
                delays.append(0.0)
                append(signal, QueueStatus.SURFACED, signal.decided_at, ("review_slot_available",))
            else:
                deferred += 1
                append(
                    signal, QueueStatus.DEFERRED, signal.decided_at, ("daily_capacity_exhausted",)
                )
    incoming = incoming_case_count or len({item.case_id for item in signals})
    slots = max(1, len(by_day) * config.daily_review_slots)
    maximum_depth = max((item.queue_depth for item in events), default=0)
    maximum_age = max((item.queue_age_minutes for item in events), default=0.0)
    denominator = incoming or 1
    metrics = CapacityMetrics(
        profile=config.profile,
        incoming_cases=incoming,
        detector_positive_cases=len(positive),
        active_recommendations=len(active),
        surfaced_recommendations=surfaced,
        reviewed_recommendations=surfaced,
        queued_recommendations=len(active),
        deferred_recommendations=deferred,
        observe_only_signals=len(observe),
        expired_in_queue=0,
        detector_positive_coverage=len(positive) / denominator,
        active_recommendation_coverage=len(active) / denominator,
        surfaced_coverage=surfaced / denominator,
        reviewed_coverage=surfaced / denominator,
        observe_only_coverage=len(observe) / denominator,
        maximum_queue_depth=maximum_depth,
        maximum_backlog_age_minutes=maximum_age,
        mean_queue_delay_minutes=mean(delays) if delays else None,
        p95_queue_delay_minutes=_percentile(delays, 0.95),
        capacity_utilisation=min(1.0, surfaced / slots),
    )
    return tuple(events), metrics


def build_queue_checkpoint(
    *,
    run_id: str,
    signals: tuple[RefinedSignal, ...],
    events: tuple[QueueEvent, ...],
    detector_fingerprint: str,
    config: ReviewerCapacityConfig,
) -> QueueCheckpoint:
    """Capture replay position and fingerprints for deterministic restart validation."""
    active_ids = tuple(
        sorted(
            {
                item.signal_id
                for item in events
                if item.status in {QueueStatus.QUEUED, QueueStatus.DEFERRED}
            }
        )
    )
    audit_root = shadow_fingerprint([item.content_fingerprint for item in events])
    content = {
        "run_id": run_id,
        "source_position": len(signals),
        "detector_fingerprint": detector_fingerprint,
        "capacity_fingerprint": config.capacity_fingerprint,
        "active_signal_ids": active_ids,
        "audit_root": audit_root,
    }
    return QueueCheckpoint(
        run_id=run_id,
        source_position=len(signals),
        detector_fingerprint=detector_fingerprint,
        capacity_fingerprint=config.capacity_fingerprint,
        pending_confirmations=(),
        queue_events=events,
        active_signal_ids=active_ids,
        audit_root=audit_root,
        checkpoint_fingerprint=shadow_fingerprint(content),
    )


def validate_queue_checkpoint(
    checkpoint: QueueCheckpoint,
    *,
    detector_fingerprint: str,
    config: ReviewerCapacityConfig,
) -> None:
    """Reject restart under changed detector or fictional capacity assumptions."""
    if checkpoint.detector_fingerprint != detector_fingerprint:
        raise ValueError("queue checkpoint detector fingerprint mismatch")
    if checkpoint.capacity_fingerprint != config.capacity_fingerprint:
        raise ValueError("queue checkpoint capacity fingerprint mismatch")
