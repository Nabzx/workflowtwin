# ADR 0007: Immutable event-level counterfactual simulation

- **Status:** Accepted
- **Date:** 2026-07-17

## Context

WorkflowTwin needs to test one eligible administrative opportunity without confusing theoretical
burden, simulated effects, and realised impact. Directly editing summary metrics would bypass process
behavior and hide failure, review, and adverse paths. A live agent or autonomous action would violate
the current evidence and safety boundary.

## Decision

Select the intervention from the controlled-prototype portfolio and version its definition and
policy. Preserve operational events as immutable source facts. Create a separate deterministic
counterfactual view that replaces eligible event histories according to explicit administrative
rules, then run the existing baseline and process engines over that view.

Model human review as delayed and costly. Require approval before a simulated change, preserve
rejection, timeout, fallback, service failure, false positive, false negative, and rollback states,
and include their burden. Make adverse scenarios mandatory and keep optimistic assumptions imperfect.
Put hard clinical, communication, sensitive-data, and source-mutation prohibitions outside any
effectiveness calculation.

Use historical missing-information paths only through a simulation-private truth oracle. Do not
expose that label to policy and do not require generator ground truth. Separate observed burden,
addressable upper bound, simulated workflow effect, control overhead, fictional cost proxies, and
nonexistent realised impact in every contract and report.

## Consequences

Simulated effects arise from event behavior and can change metrics, variants, conformance, and
bottlenecks through existing code. Source immutability, provenance, per-case randomness, and stable
fingerprints make runs auditable and reproducible. Human oversight and unfavorable outcomes remain
visible rather than being treated as free or deleted from the portfolio narrative.

The model is retrospective and assumption-dependent. It does not prove causal impact or production
feasibility, and its hidden-path oracle cannot become a deployed detector. The milestone therefore
produces only a decision about whether a future recommendation-only shadow-mode prototype may be
justified. It does not implement a live agent, external integration, autonomous communication, or
workflow automation.
