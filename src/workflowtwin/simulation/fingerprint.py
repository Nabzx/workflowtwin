"""Canonical fingerprints and stable identifiers for simulation artifacts."""

import hashlib
import json
from enum import Enum
from typing import Any
from uuid import UUID, uuid5

from pydantic import BaseModel

SIMULATION_NAMESPACE = UUID("4d5e6f70-8192-4a3b-8c5d-6e7f8091a2b3")


def canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return canonical_value(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    return value


def stable_hash(value: Any) -> str:
    payload = json.dumps(
        canonical_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def stable_id(prefix: str, value: Any, *, length: int = 16) -> str:
    return f"{prefix}-{stable_hash(value)[:length]}"


def counterfactual_event_id(*, simulation_run_id: str, source_event_id: UUID, rule: str) -> UUID:
    return uuid5(SIMULATION_NAMESPACE, f"{simulation_run_id}:{source_event_id}:{rule}")


def case_random_seed(
    *, simulation_seed: int, case_id: UUID, intervention_version: str, scenario_id: str
) -> int:
    digest = stable_hash(
        {
            "simulation_seed": simulation_seed,
            "case_id": str(case_id),
            "intervention_version": intervention_version,
            "scenario_id": scenario_id,
        }
    )
    return int(digest[:16], 16)
