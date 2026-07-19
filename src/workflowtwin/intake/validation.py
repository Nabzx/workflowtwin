"""Supported intake validation API."""

from workflowtwin.source_contracts.validation import (
    SourceContractValidation,
    validate_definition,
    validate_snapshots,
)

validate_northstar_intake = validate_snapshots

__all__ = [
    "SourceContractValidation",
    "validate_definition",
    "validate_northstar_intake",
]
