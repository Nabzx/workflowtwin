"""Benchmark-only timing-aware evaluation oracle.

This module must never be imported by ``detector.py`` or ``policy.py``.
"""

from collections import defaultdict
from datetime import datetime

from workflowtwin.shadow.models import ShadowEvaluationLabel, ShadowLabelStatus


class ShadowEvaluationOracle:
    """Resolve hidden labels after recommendations have already been produced."""

    def __init__(self, labels: tuple[ShadowEvaluationLabel, ...]) -> None:
        grouped: dict[object, list[ShadowEvaluationLabel]] = defaultdict(list)
        for label in labels:
            grouped[label.case_id].append(label)
        self._labels = {
            case_id: tuple(sorted(values, key=lambda item: (item.valid_from, item.label_id)))
            for case_id, values in grouped.items()
        }

    def label_at(self, case_id: object, as_of: datetime) -> ShadowLabelStatus:
        candidates = [
            label
            for label in self._labels.get(case_id, ())
            if label.valid_from <= as_of
            and (label.valid_until is None or as_of < label.valid_until)
        ]
        if not candidates:
            return ShadowLabelStatus.NOT_EVALUABLE
        return candidates[-1].status
