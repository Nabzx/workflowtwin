# ADR 0004: Event-semantic operational metrics before process mining

- **Status:** Accepted
- **Date:** 2026-07-16

## Context

WorkflowTwin needs a trustworthy quantitative baseline before process discovery, recommendations,
or simulation. Version 1 events are immutable point observations with event and ingestion timestamps,
manual-work flags, actors, and explicit activity types. They do not contain continuous effort traces.
Synthetic ground truth exists for benchmark evaluation but must not leak into metric calculation.

## Decision

Use event time as the source of operational truth and ingestion time only for data-quality metrics.
Construct deterministic timelines with `(event_at, event_id)` ordering. Preserve repeated activities
and deduplicate only identical source identities under an explicit policy.

Represent every case metric with a stable status, precision, unit, source event identifiers,
boundaries, exclusion reason, warnings, assumptions, and calculation version. Preserve missing values
as unavailable, excluded, or not applicable instead of replacing them with zero.

Calculate waiting as an estimated sum of explicitly paired business-calendar intervals. Calculate
processing time only as a labelled configurable manual-touch proxy until source data contains effort
boundaries. Exclude partial open ages from closed-duration aggregation.

Use transparent deterministic cohort rules before introducing AI recommendations or statistical
tests. Require minimum cohort sizes and describe differences as material or insufficient rather than
statistically significant. Run synthetic ground-truth comparison only after operational findings are
complete.

## Consequences

Results remain inspectable and reproducible, but waiting and processing are estimates rather than
observed labour time. Some valid cases will have unavailable metrics, and the quality report may be
more prominent than a simpler dashboard number. Assigned-team cohorts require an explicit structured
assignment attribute and remain unavailable for historical records without it.

The baseline analyzer loads the current benchmark into memory and uses standard-library statistics.
PM4Py, process graphs, statistical inference, prediction, and recommendations remain separate future
decisions.

