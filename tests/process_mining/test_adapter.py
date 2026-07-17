"""Tests for WorkflowTwin's boundary around PM4Py and pandas."""

from pathlib import Path
from typing import Any

import pytest

from workflowtwin.domain.referrals.fixtures import straight_through_successful_referral
from workflowtwin.process_mining.adapters.pm4py import Pm4pyAdapter, Pm4pyAdapterError
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.event_log import build_process_log
from workflowtwin.process_mining.models import ProcessLog, ProcessLogQuality

from .conftest import input_for_scenarios


def _straight_log() -> ProcessLog:
    return build_process_log(
        input_for_scenarios((straight_through_successful_referral(),)),
        ProcessMiningConfig(minimum_cohort_size=2),
    )


def test_dataframe_conversion_is_contained_and_preserves_attributes() -> None:
    frame = Pm4pyAdapter().to_dataframe(_straight_log())

    assert list(frame.columns) == [
        "case:concept:name",
        "concept:name",
        "time:timestamp",
        "workflowtwin:event_id",
        "workflowtwin:ingested_at",
        "workflowtwin:actor_type",
        "workflowtwin:service_line",
        "workflowtwin:referral_source",
    ]
    assert frame.iloc[0]["concept:name"] == "Referral submitted"
    assert frame.iloc[-1]["concept:name"] == "Referral completed"


def test_empty_log_is_rejected_for_discovery() -> None:
    empty = ProcessLog(
        activity_mapping_version="northstar-activity-map-v1",
        traces=(),
        quality=ProcessLogQuality(
            cases_received=0,
            traces_included=0,
            traces_excluded=0,
            events_received=0,
            events_included=0,
            duplicate_events_excluded=0,
            orphan_event_count=0,
            empty_case_count=0,
            unsupported_schema_cases=0,
            unsupported_mapping_count=0,
            identical_timestamp_cases=0,
            out_of_order_ingestion_cases=0,
            warnings=(),
        ),
    )

    with pytest.raises(Pm4pyAdapterError, match="empty log"):
        Pm4pyAdapter().discover(empty, ProcessMiningConfig(), {})
    assert Pm4pyAdapter().replay(empty, "northstar-strict-v1") == ()


def test_discovery_canonicalises_external_results() -> None:
    process_log = _straight_log()
    canonical = {
        (source.activity, target.activity): 1
        for source, target in zip(
            process_log.traces[0].events,
            process_log.traces[0].events[1:],
            strict=False,
        )
    }

    discovery = Pm4pyAdapter().discover(process_log, ProcessMiningConfig(), canonical)

    assert discovery.frequency_dfg == canonical
    assert discovery.result.pm4py_dfg_matches_canonical
    assert discovery.result.process_tree is not None
    assert discovery.result.petri_net_place_count > 0


class _BrokenDiscovery:
    def discover_dfg(self, _frame: Any) -> None:
        raise RuntimeError("external failure")


def test_discovery_failure_becomes_adapter_error(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = Pm4pyAdapter()
    _, pandas = adapter._modules()
    monkeypatch.setattr(adapter, "_modules", lambda: (_BrokenDiscovery(), pandas))

    with pytest.raises(Pm4pyAdapterError, match="discovery failed"):
        adapter.discover(_straight_log(), ProcessMiningConfig(), {})


class _MalformedReplay:
    def conformance_diagnostics_token_based_replay(
        self, *args: Any, **kwargs: Any
    ) -> list[dict[str, Any]]:
        return [{}]


def test_malformed_replay_is_not_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = Pm4pyAdapter()
    _, pandas = adapter._modules()
    monkeypatch.setattr(adapter, "_modules", lambda: (_MalformedReplay(), pandas))

    with pytest.raises(Pm4pyAdapterError, match="malformed diagnostics"):
        adapter.replay(_straight_log(), "northstar-strict-v1")


class _BrokenVisualisation:
    def __getattr__(self, _name: str) -> Any:
        def fail(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("Graphviz unavailable")

        return fail


def test_visualisation_failure_returns_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = Pm4pyAdapter()
    process_log = _straight_log()
    canonical = {
        (source.activity, target.activity): 1
        for source, target in zip(
            process_log.traces[0].events,
            process_log.traces[0].events[1:],
            strict=False,
        )
    }
    adapter.discover(process_log, ProcessMiningConfig(), canonical)
    _, pandas = adapter._modules()
    monkeypatch.setattr(adapter, "_modules", lambda: (_BrokenVisualisation(), pandas))

    paths, warnings = adapter.export_visualisations(tmp_path, ProcessMiningConfig())

    assert not paths
    assert len(warnings) == 4
    assert all("unavailable" in warning for warning in warnings)
