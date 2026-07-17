"""Narrow PM4Py adapter; no library objects cross this module boundary."""

from __future__ import annotations

import importlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import ProcessDiscoveryResult, ProcessLog
from workflowtwin.process_mining.reference_models import (
    GOVERNED_REFERENCE_ID,
    STRICT_REFERENCE_ID,
    STRICT_SEQUENCE,
)


class Pm4pyAdapterError(RuntimeError):
    """Raised when PM4Py returns unusable core discovery or replay output."""


@dataclass(frozen=True, slots=True)
class ReplayDiagnostic:
    case_id: str
    fitness: float
    is_fit: bool
    missing_tokens: int
    remaining_tokens: int


@dataclass(frozen=True, slots=True)
class AdapterDiscovery:
    result: ProcessDiscoveryResult
    frequency_dfg: dict[tuple[str, str], int]
    performance_dfg: dict[tuple[str, str], dict[str, float]]


class Pm4pyAdapter:
    """Convert typed logs, call stable public APIs, and canonicalise results."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Any] = {}

    @staticmethod
    def _modules() -> tuple[Any, Any]:
        os.environ.setdefault(
            "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "workflowtwin-matplotlib")
        )
        return importlib.import_module("pm4py"), importlib.import_module("pandas")

    def to_dataframe(self, process_log: ProcessLog) -> Any:
        _, pandas = self._modules()
        rows = [
            {
                "case:concept:name": str(event.case_id),
                "concept:name": event.activity,
                "time:timestamp": event.event_at,
                "workflowtwin:event_id": str(event.event_id),
                "workflowtwin:ingested_at": event.ingested_at,
                "workflowtwin:actor_type": event.actor_type,
                "workflowtwin:service_line": event.service_line,
                "workflowtwin:referral_source": event.referral_source,
            }
            for trace in process_log.traces
            for event in trace.events
        ]
        return pandas.DataFrame.from_records(rows)

    def discover(
        self,
        process_log: ProcessLog,
        config: ProcessMiningConfig,
        canonical_dfg: dict[tuple[str, str], int],
    ) -> AdapterDiscovery:
        if not process_log.traces:
            raise Pm4pyAdapterError("cannot discover a process from an empty log")
        pm4py, _ = self._modules()
        frame = self.to_dataframe(process_log)
        try:
            frequency, starts, ends = pm4py.discover_dfg(frame)
            performance, _, _ = pm4py.discover_performance_dfg(frame, perf_aggregation_key="all")
            tree = pm4py.discover_process_tree_inductive(
                frame,
                noise_threshold=config.discovery_noise_threshold,
                multi_processing=False,
            )
            net, initial_marking, final_marking = pm4py.convert_to_petri_net(tree)
        except Exception as error:
            raise Pm4pyAdapterError("PM4Py process discovery failed") from error
        frequency_dfg = {
            (str(source), str(target)): int(count) for (source, target), count in frequency.items()
        }
        performance_dfg = {
            (str(source), str(target)): {
                str(name): float(value)
                for name, value in details.items()
                if isinstance(value, (int, float))
            }
            for (source, target), details in performance.items()
        }
        self._artifacts = {
            "frame": frame,
            "frequency": frequency,
            "performance": performance,
            "starts": starts,
            "ends": ends,
            "tree": tree,
            "discovered_net": (net, initial_marking, final_marking),
        }
        return AdapterDiscovery(
            result=ProcessDiscoveryResult(
                algorithm="pm4py_inductive_miner",
                noise_threshold=config.discovery_noise_threshold,
                discovered=True,
                process_tree=str(tree),
                petri_net_place_count=len(net.places),
                petri_net_transition_count=len(net.transitions),
                pm4py_dfg_matches_canonical=frequency_dfg == canonical_dfg,
                warnings=(
                    ()
                    if frequency_dfg == canonical_dfg
                    else ("PM4Py and canonical directly-follows counts differ",)
                ),
            ),
            frequency_dfg=frequency_dfg,
            performance_dfg=performance_dfg,
        )

    def _reference_net(self, reference_id: str) -> tuple[Any, Any, Any]:
        petri_obj = importlib.import_module("pm4py.objects.petri_net.obj")
        petri_utils = importlib.import_module("pm4py.objects.petri_net.utils.petri_utils")
        net = petri_obj.PetriNet(reference_id)
        places: dict[str, Any] = {}

        def place(name: str) -> Any:
            if name not in places:
                places[name] = petri_obj.PetriNet.Place(name)
                net.places.add(places[name])
            return places[name]

        def transition(source: str, target: str, activity: str, suffix: str = "") -> None:
            item = petri_obj.PetriNet.Transition(f"{source}-{target}-{activity}-{suffix}", activity)
            net.transitions.add(item)
            petri_utils.add_arc_from_to(place(source), item, net)
            petri_utils.add_arc_from_to(item, place(target), net)

        if reference_id == STRICT_REFERENCE_ID:
            for index, activity in enumerate(STRICT_SEQUENCE):
                transition(f"p{index}", f"p{index + 1}", activity)
            final_place = f"p{len(STRICT_SEQUENCE)}"
        elif reference_id == GOVERNED_REFERENCE_ID:
            transition("p0", "p1", "Referral submitted")
            transition("p1", "p2", "Referral received")
            transition("p2", "p3", "Completeness checked")
            transition("p3", "p4", "Missing information requested")
            transition("p4", "p2", "Missing information received")
            transition("p4", "p4", "Patient no response")
            transition("p3", "p5", "Referral categorised")
            transition("p5", "p5", "Referral recategorised")
            transition("p5", "p6", "Clinical team assigned")
            transition("p6", "p6", "Clinical team reassigned")
            transition("p6", "p7", "Scheduling started")
            transition("p7", "p6", "Scheduling failed")
            transition("p7", "p7", "Patient no response", "scheduling")
            transition("p7", "p8", "Appointment booked")
            transition("p8", "p9", "Patient notified")
            transition("p9", "end", "Referral completed")
            for index, state in enumerate(("p2", "p3", "p4")):
                transition(state, "end", "Referral rejected", str(index))
            for index, state in enumerate(("p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9")):
                transition(state, "end", "Referral cancelled", str(index))
            for index, state in enumerate(("p4", "p6", "p7", "p8", "p9")):
                transition(state, "end", "Referral closed other", str(index))
            final_place = "end"
        else:
            raise ValueError(f"unknown reference model: {reference_id}")
        initial = petri_obj.Marking({place("p0"): 1})
        final = petri_obj.Marking({place(final_place): 1})
        return net, initial, final

    def replay(self, process_log: ProcessLog, reference_id: str) -> tuple[ReplayDiagnostic, ...]:
        if not process_log.traces:
            return ()
        pm4py, _ = self._modules()
        frame = self.to_dataframe(process_log)
        net, initial, final = self._reference_net(reference_id)
        try:
            diagnostics = pm4py.conformance_diagnostics_token_based_replay(
                frame,
                net,
                initial,
                final,
                opt_parameters={"show_progress_bar": False},
            )
        except Exception as error:
            raise Pm4pyAdapterError(f"PM4Py replay failed for {reference_id}") from error
        if len(diagnostics) != len(process_log.traces):
            raise Pm4pyAdapterError("PM4Py replay returned the wrong trace count")
        results = []
        for trace, diagnostic in zip(process_log.traces, diagnostics, strict=True):
            try:
                results.append(
                    ReplayDiagnostic(
                        case_id=str(trace.case_id),
                        fitness=float(diagnostic["trace_fitness"]),
                        is_fit=bool(diagnostic["trace_is_fit"]),
                        missing_tokens=int(diagnostic["missing_tokens"]),
                        remaining_tokens=int(diagnostic["remaining_tokens"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise Pm4pyAdapterError("PM4Py replay returned malformed diagnostics") from error
        self._artifacts[f"reference:{reference_id}"] = (net, initial, final)
        return tuple(results)

    def export_visualisations(
        self, directory: Path, config: ProcessMiningConfig
    ) -> tuple[tuple[Path, ...], tuple[str, ...]]:
        pm4py, _ = self._modules()
        if not self._artifacts:
            return (), ("visualisations unavailable before successful discovery",)
        directory.mkdir(parents=True, exist_ok=True)
        paths = []
        warnings = []

        def render(name: str, function: Any, *args: Any, **kwargs: Any) -> None:
            path = directory / f"{name}.svg"
            try:
                function(*args, str(path), **kwargs)
                paths.append(path)
            except Exception as error:
                warnings.append(f"{name} visualisation unavailable: {type(error).__name__}")

        filtered_frequency = {
            edge: count
            for edge, count in self._artifacts["frequency"].items()
            if count >= config.visualisation_minimum_frequency
        }
        filtered_performance = {
            edge: details
            for edge, details in self._artifacts["performance"].items()
            if edge in filtered_frequency
        }
        render(
            "frequency-dfg",
            pm4py.save_vis_dfg,
            filtered_frequency,
            self._artifacts["starts"],
            self._artifacts["ends"],
            max_num_edges=config.visualisation_maximum_edges,
        )
        render(
            "performance-dfg",
            pm4py.save_vis_performance_dfg,
            filtered_performance,
            self._artifacts["starts"],
            self._artifacts["ends"],
            aggregation_measure="median",
        )
        render("discovered-process-tree", pm4py.save_vis_process_tree, self._artifacts["tree"])
        discovered_net, discovered_initial, discovered_final = self._artifacts["discovered_net"]
        render(
            "discovered-petri-net",
            pm4py.save_vis_petri_net,
            discovered_net,
            discovered_initial,
            discovered_final,
        )
        for name, values in sorted(self._artifacts.items()):
            if not name.startswith("reference:"):
                continue
            net, initial, final = values
            render(name.split(":", 1)[1], pm4py.save_vis_petri_net, net, initial, final)
        return tuple(paths), tuple(warnings)
