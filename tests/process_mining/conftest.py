"""Shared process-mining test inputs."""

from collections.abc import Iterable

from workflowtwin.analytics.fingerprint import dataset_fingerprint
from workflowtwin.analytics.models import AnalysisInput
from workflowtwin.domain.referrals.fixtures import ReferralScenario


def input_for_scenarios(scenarios: Iterable[ReferralScenario]) -> AnalysisInput:
    selected = tuple(scenarios)
    cases = tuple(scenario.case for scenario in selected)
    events = tuple(event for scenario in selected for event in scenario.events)
    return AnalysisInput(
        cases=cases,
        events=events,
        dataset_fingerprint=dataset_fingerprint(cases, events),
        generation_run_id=None,
        manifest=None,
        ground_truth=None,
    )
