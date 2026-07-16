# ADR 0003: Deterministic synthetic generation and run tracking

- **Status:** Accepted
- **Date:** 2026-07-16

## Context

WorkflowTwin needs realistic but inspectable fictional event logs with known signals. Future analysis
must be evaluated without learning labels from operational event payloads. Persistence must tolerate
CLI retries without creating another dataset or weakening append-only event constraints.

## Decision

Use Python's standard-library `random.Random` with one explicitly owned instance per run. Generate
existing `ReferralCase` and `ReferralEvent` contracts and derive UUID5 identities from run identity
and sequence. Model timing with a small working-calendar helper rather than a simulation framework.

Export ground truth separately from operational contracts. Keep duplicate-source attempts only in
ground truth while the canonical event remains persistable. Compute the dataset fingerprint as
SHA-256 over canonical, ordered case and event JSON; exclude manifest creation time and ground truth.

Add `synthetic_generation_runs` for idempotency and audit state. Reserve a run, persist data in one
transaction with batched flushes, and commit completion with its manifest. Record failure after a
rollback. A completed run identifier cannot be reused for a different fingerprint.

## Consequences

Generation is reproducible without NumPy, Faker, pandas, or an external simulator. UUIDs and logical
output remain stable across machines running compatible Python and schema versions. Changing
generation logic requires a generator-version change and may change fingerprints even with the same
seed.

The generator holds one logical dataset in memory before optional persistence; batching bounds
database unit-of-work growth but not generation memory. This is suitable for the current 10,000 to
25,000 case target, not millions of cases. The run table is audit state, not a general job system.

Ground truth can be joined by identifiers during evaluation, so evaluation code must keep it outside
feature construction. Fingerprints cover operational data rather than labels, allowing label fixes
without pretending the underlying event log changed.

