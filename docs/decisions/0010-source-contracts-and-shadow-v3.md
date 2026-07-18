# ADR 0010: Analyse source observability before strict-v3

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

The frozen `strict-v2` preserved precision but failed its recall gate on an immutable holdout. A
missed positive can reflect unavailable, ambiguous, late, stale, conflicting, unsupported, or
policy-prohibited information rather than a bad detector threshold. Reusing the old holdout to choose
new rules would leak evaluation evidence into development.

## Decision

Keep `strict-v1`, `strict-v2`, their fingerprints, and the old holdout unchanged. Introduce a
separate V2 administrative source contract before considering detector changes. V2 distinguishes
unknown from explicit absence, requires applicability and provenance, versions form requirements,
records source event and availability time, and represents freshness, conflict, warnings, manual
review, producer identity, and supersession. Generator truth remains separate from published source
state and evaluation labels.

Calculate case-level observability and recall ceilings only after source publication is frozen. Use
those ceilings to interpret recall, never to drive runtime decisions. Require realistic producer and
availability semantics for every field and reject clinical or identifying content.

Because historical source replay showed meaningful recoverable recall, register `strict-v3` with
new development, validation, and holdout seeds before implementing it. Permit only deterministic V2
administrative rules. Keep authority recommendation-only. Lock detector, policy, requirements,
source, and capacity fingerprints only if validation passes; otherwise leave the new holdout sealed.

## Consequences

- V1 and V2 historical behavior stays reproducible; compatibility views do not reinterpret unknown.
- Source omissions and detector misses can be discussed separately.
- Recall is accompanied by an observable ceiling and a ceiling-relative measure.
- Stale, conflicting, unsupported, and unknown evidence causes explicit abstention.
- A better source representation does not guarantee acceptable recommendation volume or production quality.
- Validation V3 failed the detector-coverage gate, so no strict-v3 lock or holdout result exists.
- The system remains in shadow mode with no workflow action, LLM, machine learning, or deployment authority.

## Rejected alternatives

- Continue tuning `strict-v2`, because it and its holdout result are frozen.
- Treat unknown as absence, because that invents evidence and risks false positives.
- Add label-revealing synthetic fields, because they would not describe a plausible source system.
- Resolve source conflicts with eventual outcomes, because that leaks future evaluation truth.
- Open holdout V3 after a partial validation pass, because every mandatory gate was pre-registered.
- Start a limited-action pilot, because validation did not authorise one.
