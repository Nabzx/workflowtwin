"""Machine-readable fictional administrative form requirements."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from workflowtwin.domain.referrals.enums import SourceSystem
from workflowtwin.source_contracts.models import (
    ALLOWED_FIELD_IDS,
    FICTIONAL_DECLARATION,
    SourceContractModel,
)


class RequirementKind(StrEnum):
    FIELD = "field"
    DOCUMENT = "document"
    ACKNOWLEDGEMENT = "acknowledgement"
    ROUTING_CONTACT = "routing_contact"


class AdministrativeCondition(SourceContractModel):
    field_id: str
    equals: str

    @field_validator("field_id")
    @classmethod
    def field_must_be_administrative(cls, value: str) -> str:
        if value not in ALLOWED_FIELD_IDS:
            raise ValueError(f"unsupported administrative condition field: {value}")
        return value


class RequirementRule(SourceContractModel):
    requirement_id: str
    field_id: str
    kind: RequirementKind
    required: bool
    condition: AdministrativeCondition | None = None
    administrative_purpose: str

    @field_validator("field_id")
    @classmethod
    def field_must_be_supported(cls, value: str) -> str:
        if value not in ALLOWED_FIELD_IDS:
            raise ValueError(f"unsupported requirement field: {value}")
        return value


class FormRequirements(SourceContractModel):
    form_identifier: str
    form_version: str
    administrative_path: str
    requirements: tuple[RequirementRule, ...]
    source_supported_fields: dict[SourceSystem, tuple[str, ...]]
    source_exceptions: dict[SourceSystem, tuple[str, ...]] = Field(default_factory=dict)
    unsupported_source_combinations: tuple[SourceSystem, ...] = ()
    effective_from: datetime
    effective_until: datetime | None = None

    @model_validator(mode="after")
    def validate_effective_period(self) -> "FormRequirements":
        if self.effective_from.tzinfo is None or self.effective_from.utcoffset() is None:
            raise ValueError("requirements effective_from must be timezone-aware")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("requirements effective_until must follow effective_from")
        identifiers = [item.requirement_id for item in self.requirements]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("requirement identifiers must be unique per form")
        for fields in self.source_supported_fields.values():
            unsupported = set(fields) - ALLOWED_FIELD_IDS
            if unsupported:
                raise ValueError(f"source declares unsupported fields: {sorted(unsupported)}")
        return self


class AdministrativeRequirementsContract(SourceContractModel):
    contract_id: str
    contract_version: str
    forms: tuple[FormRequirements, ...]
    provenance_references: tuple[str, ...]
    fictional_declaration: str = FICTIONAL_DECLARATION

    @model_validator(mode="after")
    def validate_contract(self) -> "AdministrativeRequirementsContract":
        if self.fictional_declaration != FICTIONAL_DECLARATION:
            raise ValueError("requirements contract must declare fictional data")
        if not self.provenance_references:
            raise ValueError("requirements contract requires provenance")
        keys = [(item.form_identifier, item.form_version) for item in self.forms]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate form-version requirements")
        return self

    def requirements_for(
        self,
        *,
        form_identifier: str,
        form_version: str,
        source_system: SourceSystem,
        as_of: datetime,
    ) -> FormRequirements | None:
        return next(
            (
                item
                for item in self.forms
                if item.form_identifier == form_identifier
                and item.form_version == form_version
                and item.effective_from <= as_of
                and (item.effective_until is None or as_of < item.effective_until)
                and source_system not in item.unsupported_source_combinations
            ),
            None,
        )

    def required_rules(
        self, form: FormRequirements, explicit_values: dict[str, str]
    ) -> tuple[RequirementRule, ...]:
        result = []
        for rule in form.requirements:
            if not rule.required:
                continue
            if rule.condition is None or explicit_values.get(rule.condition.field_id) == (
                rule.condition.equals
            ):
                result.append(rule)
        return tuple(result)
