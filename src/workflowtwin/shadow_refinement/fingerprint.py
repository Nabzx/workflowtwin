"""Stable refinement identifiers built on canonical shadow hashing."""

from typing import Any

from workflowtwin.shadow.fingerprint import shadow_fingerprint, shadow_id

__all__ = ["shadow_fingerprint", "shadow_id"]


def locked_fingerprint(value: Any) -> str:
    return shadow_fingerprint(value)
