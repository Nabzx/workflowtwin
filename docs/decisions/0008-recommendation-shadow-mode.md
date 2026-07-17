# ADR 0008: Use ingestion-ordered, recommendation-only shadow mode

- Status: accepted
- Date: 2026-07-18

## Context

Counterfactual simulation of structured completeness review showed mixed results. Reduced manual
touches and earlier checks did not reliably offset human-review, fallback, and failure overhead. The
10,000-case central simulation recommended revising the design, not changing a workflow.

The operational event model also lacks explicit, structured intake evidence before the first manual
completeness decision. Later missing-information events and final outcomes are useful evaluation
evidence but would leak future information into an online detector.

## Decision

Build a separate recommendation-only shadow system around versioned fictional intake snapshots.
Order inputs by source availability (`available_at`, equivalent to `ingested_at`), deterministic
source priority, and stable identity. Expose only an as-of-time structured administrative projection
to the detector. Keep hidden labels and the benchmark reviewer behind a separate oracle boundary.

Default to a strict deterministic profile that prioritises explicit evidence and precision over
coverage. Treat abstention as a first-class result. Require human review for every recommendation.
Keep lifecycle and audit history append-only and hash chained. Make policy, audit, precision, burden,
capacity, and reliability thresholds mandatory promotion gates.

Do not use an LLM, predictive model, workflow engine, background queue, or shadow persistence tables.
PostgreSQL loading is read-only; shadow outputs are file-backed and cannot update operational cases.

## Rationale

- **Recommendation only:** the simulation did not justify action and the milestone asks whether a
  later human-reviewed pilot is worth considering, not whether autonomy is safe.
- **Precision before coverage:** false-positive reviews consume the same scarce administrative time
  that the intervention aims to protect.
- **Ingestion time:** an online claim must reflect when WorkflowTwin could observe a fact, not when a
  source later says it occurred.
- **Separate snapshots:** operational events do not contain enough pre-decision evidence; adding
  fictional intake fields to event metadata would blur source facts and outcomes.
- **Isolated oracle:** future outcomes can grade a completed recommendation but cannot help create it.
- **Abstention:** forcing a binary result on unknown, conflicting, stale, or unsupported input would
  manufacture confidence and burden.
- **Reviewer burden gate:** high precision can still overwhelm a team if recommendation volume is too
  high.
- **Audit and policy blockers:** a recommendation without provenance or permission is unsafe even if
  statistically accurate.
- **No LLM:** deterministic structured rules are sufficient, easier to audit, and avoid clinical or
  free-text expansion of scope.

## Consequences

The detector can be evaluated reproducibly, replayed from a checkpoint, and compared across strict,
balanced, and exploratory profiles without operational effect. Its limits are visible: coverage is
lower, unsupported inputs abstain, hidden labels are synthetic, and file-backed review ingestion is
not a production service.

Any later milestone must follow the promotion assessment. A failed mandatory gate requires detector
revision or continued shadow evaluation. A passed assessment would authorise only design of a narrow,
fictional, reversible, human-approved pilot after separate governance review.
