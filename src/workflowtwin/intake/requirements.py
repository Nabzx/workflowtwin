"""Product names and loader for the supported Northstar requirements contract."""

from pathlib import Path

from workflowtwin.source_contracts.io import load_requirements
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract

DEFAULT_REQUIREMENTS_PATH = Path("config/intake/northstar-requirements.json")
NorthstarRequirementsContract = AdministrativeRequirementsContract


def load_northstar_requirements(
    path: Path = DEFAULT_REQUIREMENTS_PATH,
) -> AdministrativeRequirementsContract:
    return load_requirements(path)
