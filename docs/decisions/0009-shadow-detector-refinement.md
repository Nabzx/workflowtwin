# ADR 0009: Version detector refinement and separate review capacity

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

The fictional Northstar strict shadow detector produced administratively relevant recommendations,
but transient source corrections and already-resolving cases created avoidable review burden. A
capacity limit could hide that burden without improving detector quality.

## Decision

Freeze the existing strict rules as `strict-v1`. Introduce `strict-v2` as a distinct, fingerprinted
detector which confirms explicit supporting-document absence after 120 minutes of logical time.
Resolve a concern if a current source snapshot supplies the document during that window. Use only
facts available as of the decision time.

When explicitly supplied, source conflicts cause abstention and an overlapping warning or existing
manual review moves the signal to observe-only. The benchmark does not fabricate those fields, so
these controls remain inactive unless an input contract provides them.

Run deterministic priority and capacity control after detection. Preserve detector-positive,
active, surfaced, reviewed, deferred, observe-only, and expired states separately. Capacity never
changes the detector confusion matrix. All capacity profiles and review times are fictional.

Pre-register two development splits, one validation split, and one untouched 10,000-case holdout.
Write a detector lock before opening the holdout, permit restart under the same lock, and reject a
different fingerprint. Holdout findings must not change `strict-v2`.

## Consequences

- The wait adds 120 minutes of explicit recommendation latency.
- Precision, recall, burden, cohort stability, chronology, and capacity have separate gates.
- Missed positives remain visible; lower surfaced volume is not presented as higher quality.
- The system stays file-backed, deterministic, recommendation-only, and unable to write referrals.
- Any later rule change requires a new detector version and untouched evaluation protocol.

## Rejected alternatives

- Hard-capping detector positives, because it conceals low-quality output.
- Using source, service line, or referral type as a risk proxy.
- Inferring manual review from later events or using hidden labels in detection or priority.
- Adding an LLM, learned model, workflow engine, production queue, or database tables.
