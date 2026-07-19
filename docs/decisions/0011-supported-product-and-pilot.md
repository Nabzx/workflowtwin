# ADR 0011: Consolidate one product path and isolate human-approved pilot actions

- **Status:** Accepted
- **Date:** 2026-07-19

## Context

The repository contained strict-v1, strict-v2, and strict-v3 as similarly prominent runtime paths.
That accurately recorded research iteration but obscured which path a product user should run.
Strict-v3 achieved strong precision, recall relative to source observability, and safety, yet failed
its original pre-registered detector-positive coverage gate. That immutable result is
`strict_v3_validation_failed`; its unused holdout was not opened.

The next question is not another detector tuning round. It is whether a small, capacity-limited,
human-reviewed administrative action can be demonstrated with reliable controls and evidence.

## Decision

Support one intake contract and one detector:

- expose `IncomingReferralSnapshotV2` as the **Northstar intake contract**;
- expose unchanged strict-v3 logic as **completeness-review-detector-v1**;
- retain the strict-v3 name and fingerprint as explicit lineage metadata;
- calculate the product alias fingerprint from the alias and original/source/requirements lineage;
- remove V1/V2 executors and V3 research, validation, lock, and holdout orchestration from normal
  runtime, CLI help, configuration, scripts, and tests.

Git history, the annotated `shadow-evaluation-complete` tag, compact golden artifacts, and the
detector-evolution document preserve the experimental evidence. We do not duplicate the historical
implementation in an archive directory or reinterpret V1 data with V2 semantics.

Introduce a separate `northstar-fictional-pilot-policy-v1`. It does not modify the historical V3
protocol. It reports detector-positive coverage while controlling reviewer capacity through
surfaced recommendations, completed reviews, review minutes, false-positive review minutes, queue
depth, latency, expiry, and backlog.

Permit only one action: creating an administrative missing-information draft task in a local mock
system after explicit human approval. Templates are deterministic and use no LLM. Stable action keys
provide idempotency. Every committed action supports append-only, idempotent rollback. Pilot code
cannot send a message, reject or route a referral, change a service line, infer clinical content, or
write operational event state.

## Consequences

- Recruiters and developers see one supported product path and a substantially smaller CLI.
- Experiment results stay auditable without retaining thousands of lines of dead benchmark runtime.
- The supported alias is honest about strict-v3 lineage and does not imply a first implementation.
- Capacity policy reflects work actually surfaced to reviewers while raw detector volume stays
  transparent.
- The pilot demonstrates human control, audit, idempotency, and recovery without claiming production
  safety or deployment readiness.
- The in-memory adapter is intentionally process-local; durability and authentication remain future
  productisation work.
- No new database migration is needed because pilot actions are isolated from operational tables.

## Rejected alternatives

- **Build strict-v4:** further tuning is not the product question and risks evaluation overfitting.
- **Open the V3 holdout:** validation did not pass the pre-registered protocol.
- **Rewrite V3 as successful:** this would destroy trustworthy experiment history.
- **Keep all commands under the main CLI:** equal prominence makes experimental code look supported.
- **Use an LLM for drafts:** deterministic administrative templates are safer, testable, and enough.
- **Send to a real system:** the portfolio milestone cannot justify external communication authority.
- **Write pilot actions into operational tables:** this would weaken isolation and reversibility.
