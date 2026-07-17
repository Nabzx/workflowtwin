"""Stable identities and canonical hashes for shadow-mode artefacts."""

from typing import Any

from pydantic_core import to_jsonable_python

from workflowtwin.simulation.fingerprint import stable_hash


def shadow_fingerprint(value: Any) -> str:
    """Hash logical content with the repository's canonical JSON rules."""
    return stable_hash(to_jsonable_python(value))


def shadow_id(prefix: str, *parts: object, length: int = 16) -> str:
    """Build a readable deterministic identifier from canonical content."""
    return f"{prefix}-{stable_hash(parts)[:length]}"
