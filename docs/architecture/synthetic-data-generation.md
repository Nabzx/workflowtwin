# Synthetic data generation

Northstar Clinics, every generated referral, every actor identifier, and every result described here
is fictional. The generator creates administrative workflow data only. It does not create patient
identities, diagnoses, clinical narrative, treatment decisions, risk scores, or clinical priorities.

## Purpose

The generator creates reproducible case-level event histories for evaluating future process
reconstruction and operational analysis. It is intentionally a small domain simulator, not a random
row factory or a general discrete-event simulation framework.

```text
GenerationConfig + preset
          |
  explicit random.Random
          |
 business calendar + scenario rules
          |
 ReferralCase / ReferralEvent contracts
       /                \
ground truth         manifest + validation
       \                /
       optional artifact export
                |
      optional batch persistence
```

## Determinism

One `random.Random` instance is created per generation. UUID5 identifiers are derived from the
resolved generation-run identifier, case index, and event index. The same effective configuration,
seed, and run identifier produce identical cases, events, ground truth, and dataset fingerprint.
The manifest's wall-clock `generated_at` timestamp is not part of the fingerprint.

## Timing model

Referral arrival days use documented weekday weights and gentle alternating weekly volume factors.
Arrival hours include a minority of out-of-hours submissions. Administrative work is moved to the
next configured working period and durations consume working hours across evenings and weekends.
External information responses use elapsed time and may arrive outside working hours; subsequent
staff work waits for the calendar. Reassignment, missing-information loops, and failed scheduling
each add their own delay.

UTC is stored in domain contracts. The configured IANA timezone controls local working hours and
weekend behaviour before timestamps are converted to UTC.

## Default planted signals

| Signal | Default segment | Intended effect |
| --- | --- | --- |
| Incomplete referrals | GP practice referrals | more information loops, manual touches, and elapsed time |
| Assignment congestion | Neurology service line | longer categorisation-to-assignment wait and booking time |
| Scheduling friction | Respiratory service line | more failed attempts, manual work, delay, and cancellation exposure |
| Handoff cost | Dermatology service line | more team reassignments, handoffs, touches, and cycle time |

The relationships are probabilistic and coexist with background variation. Ground truth records the
cases actually affected; category membership alone is not treated as proof that a scenario occurred.

## Valid data-quality defects

The generator can model delayed ingestion, event/ingestion ordering differences, missing optional
actor identifiers, unexpected but valid channels, structurally valid source inconsistencies, and
source retries. Duplicate source attempts are stored in ground truth and the manifest but omitted
from canonical operational events, because `(source_system, external_event_id)` is deliberately
unique in PostgreSQL. This tests deduplication without weakening production constraints.

All normal generated records pass the existing domain contracts. Invalid inputs for rejection tests
are created directly in tests and never mixed into the default dataset.

## Ground truth and manifests

Ground truth is a separate artifact keyed by stable case and event identifiers. It records generation
paths, intended outcomes, planted bottlenecks, rework, handoffs, stuck cases, delayed events, and
duplicate attempts. Operational event metadata contains only generation provenance, never scenario
or bottleneck labels.

The manifest reports configured targets separately from realised counts and rates. Its fingerprint
is SHA-256 over canonical JSON representations of ordered cases and events. Expected findings are
qualitative hypotheses for later evaluation, not claimed analytical results.

## Persistence

`synthetic_generation_runs` records run status, effective configuration, manifest, fingerprint, and
failure context. Persistence first reserves the run identifier. Cases and canonical events are then
flushed in configured batches inside one database transaction. Completion status and manifest are
committed with the data. A failure rolls back all operational rows and marks the reserved run failed
in a separate transaction.

Rerunning a completed run with the same fingerprint returns `already_completed`. Reusing its run
identifier for different data fails clearly. Stable identifiers and the generation-run record provide
idempotency; immutable referral events remain unchanged.

## Presets

- `tiny`: 30 cases for inspection and tests.
- `demo`: 1,000 cases for local demonstrations.
- `full`: 10,000 cases for process-analysis benchmarks.

Large generated artifacts belong under ignored `artifacts/generation/` and are not committed.

