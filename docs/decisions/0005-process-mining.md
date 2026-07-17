# ADR 0005: Isolated PM4Py process reconstruction

- **Status:** Accepted
- **Date:** 2026-07-17

## Context

WorkflowTwin needs observed variants, transition evidence, structured discovery, and reference
conformance after establishing an event-semantic baseline. PM4Py provides proven process-mining
algorithms but exposes library-specific logs, pandas frames, process trees, Petri nets, and replay
diagnostics. Those types should not become application contracts.

## Decision

Place PM4Py behind one adapter that accepts a typed canonical process log and returns plain typed
WorkflowTwin results. Use a directly-follows graph for explainable frequency/performance evidence,
one Inductive Miner model for structured discovery, and token-based replay for practical deterministic
strict/governed conformance. Encode both reference workflows as versioned Petri-net specifications:
one strict successful path and one governed administrative model with documented exceptions.

Report conformance separately from elapsed performance. Generate deterministic process candidates
with materiality rules and no causal or statistical-significance claim. Evaluate synthetic ground
truth only after all operational outputs exist. Persist no raw PM4Py objects.

## Consequences

Application code remains independent of PM4Py and pandas, outputs stay inspectable, and a future
adapter upgrade has a narrow blast radius. Token replay and a policy reference simplify the governed
model but do not prove optimal ordering or operational quality. Optional Graphviz rendering can fail
without invalidating discovery. The benchmark remains in memory and is not a production job system.
PM4Py 2.7.23.2 is pinned for reproducibility. Its community release is AGPL-3.0, so commercial
distribution or network deployment requires a separate licensing review and potentially a
commercial PM4Py license.
