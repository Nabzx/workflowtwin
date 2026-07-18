"""Stable fingerprints for source and requirements contracts."""

from typing import Any

from workflowtwin.shadow.fingerprint import shadow_fingerprint


def source_contract_fingerprint(value: Any) -> str:
    return shadow_fingerprint(value)
