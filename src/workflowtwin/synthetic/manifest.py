"""Stable fingerprinting and manifest construction."""

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta

from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent
from workflowtwin.synthetic.config import GenerationConfig
from workflowtwin.synthetic.models import GenerationGroundTruth, GenerationManifest

GENERATOR_VERSION = "1.0.0"
FICTIONAL_CONFIRMATION = (
    "Northstar Clinics and every generated organisation, actor, referral, and event are fictional."
)
EXPECTED_FINDINGS = (
    "GP practice referrals should show lower first-pass completeness and longer information waits.",
    "Neurology should show longer categorisation-to-team-assignment waiting time.",
    "Respiratory should show more failed scheduling attempts and longer booking time.",
    "Dermatology reassignment paths should show more handoffs, touches, and cycle time.",
)


def dataset_fingerprint(cases: tuple[ReferralCase, ...], events: tuple[ReferralEvent, ...]) -> str:
    """Hash canonical ordered operational contracts, excluding synthetic labels."""
    payload = {
        "cases": [case.model_dump(mode="json") for case in cases],
        "events": [event.model_dump(mode="json") for event in events],
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def build_manifest(
    *,
    config: GenerationConfig,
    run_id: str,
    cases: tuple[ReferralCase, ...],
    events: tuple[ReferralEvent, ...],
    ground_truth: GenerationGroundTruth,
    generated_at: datetime,
) -> GenerationManifest:
    """Summarise targets, realised output, labels, and stable identity."""
    outcome_counts = Counter(case.status.value for case in cases)
    scenario_counts = Counter(
        path for annotation in ground_truth.cases for path in annotation.intended_path
    )
    source_system_counts = Counter(event.source_system.value for event in events)
    service_line_counts = Counter(case.service_line.value for case in cases)
    referral_source_counts = Counter(case.referral_source.value for case in cases)
    bottleneck_counts = Counter(
        label.value for annotation in ground_truth.cases for label in annotation.bottlenecks
    )
    defect_counts = Counter(
        defect.value for annotation in ground_truth.cases for defect in annotation.defects
    )
    realised_defect_rates = {
        name: count / len(cases) for name, count in sorted(defect_counts.items())
    }
    configured_defect_rates = {
        name: float(value)
        for name, value in config.deviations.model_dump(mode="json").items()
        if name
        in {
            "duplicate_source_event",
            "delayed_ingestion",
            "out_of_order_ingestion",
            "missing_optional_actor",
            "unexpected_channel",
            "source_identifier_inconsistency",
            "source_retry",
        }
    }
    return GenerationManifest(
        generator_version=GENERATOR_VERSION,
        schema_version=1,
        random_seed=config.seed,
        generation_run_id=run_id,
        configuration=config.model_dump(mode="json"),
        generated_case_count=len(cases),
        generated_event_count=len(events),
        period_start=config.period_start,
        period_end=config.period_start + timedelta(days=config.operating_days),
        outcome_counts=dict(sorted(outcome_counts.items())),
        scenario_counts=dict(sorted(scenario_counts.items())),
        source_system_distribution=dict(sorted(source_system_counts.items())),
        service_line_distribution=dict(sorted(service_line_counts.items())),
        referral_source_distribution=dict(sorted(referral_source_counts.items())),
        planted_bottlenecks=dict(sorted(bottleneck_counts.items())),
        configured_defect_rates=configured_defect_rates,
        realised_defect_counts=dict(sorted(defect_counts.items())),
        realised_defect_rates=realised_defect_rates,
        expected_qualitative_findings=EXPECTED_FINDINGS,
        dataset_fingerprint=dataset_fingerprint(cases, events),
        generated_at=generated_at,
        fictional_data_confirmation=FICTIONAL_CONFIRMATION,
    )
