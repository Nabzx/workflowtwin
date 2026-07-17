"""Deterministic loading, validation, and fingerprinting of fictional research."""

import hashlib
import json
import re
from pathlib import Path

from workflowtwin.opportunities.models import ResearchPack

FICTIONAL_DECLARATION = (
    "This is fictional synthetic user-research material created for software evaluation and "
    "demonstration."
)
FORBIDDEN_CLINICAL_TERMS = {
    "diagnose",
    "diagnosis",
    "clinical urgency",
    "treatment decision",
    "patient prognosis",
    "clinical prioritisation",
}
SENSITIVE_PATTERNS = (
    re.compile(r"\b\d{3}[- ]?\d{3}[- ]?\d{4}\b"),
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b(?:nhs|patient)\s*(?:number|name|id)\s*[:=]", re.IGNORECASE),
)


def research_pack_fingerprint(pack: ResearchPack) -> str:
    canonical = json.dumps(pack.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate_research_pack(pack: ResearchPack, *, expected_version: str) -> None:
    if pack.pack_version != expected_version:
        raise ValueError(f"unsupported research pack version: {pack.pack_version}")
    if pack.fictional_data_declaration != FICTIONAL_DECLARATION:
        raise ValueError("research pack is missing the required fictional-data declaration")
    session_ids = [session.session_id for session in pack.sessions]
    participant_ids = [session.participant_id for session in pack.sessions]
    observation_ids = [
        observation.observation_id
        for session in pack.sessions
        for observation in session.observations
    ]
    for name, values in (
        ("session", session_ids),
        ("participant", participant_ids),
        ("observation", observation_ids),
    ):
        if len(values) != len(set(values)):
            raise ValueError(f"research {name} identifiers must be unique")
    known_observations = set(observation_ids)
    for session in pack.sessions:
        for observation in session.observations:
            if observation.affected_role is not session.role:
                raise ValueError(
                    f"observation role does not match session: {observation.observation_id}"
                )
            unknown = set(observation.contradicts) - known_observations
            if unknown:
                raise ValueError(
                    f"unknown contradicting observation for {observation.observation_id}: "
                    f"{sorted(unknown)[0]}"
                )
    serialized = json.dumps(pack.model_dump(mode="json"), sort_keys=True).lower()
    for term in FORBIDDEN_CLINICAL_TERMS:
        if term in serialized:
            raise ValueError(f"research pack contains a prohibited clinical claim: {term}")
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(serialized):
            raise ValueError("research pack contains a possible direct patient identifier")


def load_research_pack(path: Path, *, expected_version: str) -> ResearchPack:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pack = ResearchPack.model_validate(payload)
    validate_research_pack(pack, expected_version=expected_version)
    return pack
