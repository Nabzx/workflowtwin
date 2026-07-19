"""Canonical identifiers shared by supported product components."""

from typing import Any

from pydantic_core import to_jsonable_python

from workflowtwin.simulation.fingerprint import stable_hash


def fingerprint(value: Any) -> str:
    return stable_hash(to_jsonable_python(value))


def stable_id(prefix: str, *parts: object, length: int = 16) -> str:
    return f"{prefix}-{stable_hash(parts)[:length]}"
