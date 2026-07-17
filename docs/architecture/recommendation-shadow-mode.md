# Recommendation-only shadow mode

## Purpose and boundary

WorkflowTwin replays fictional Northstar Clinics intake information and asks one bounded question:
does current, structured administrative evidence justify recommending a human completeness review?
The detector cannot change a case, append an operational referral event, route work, reject or approve
a referral, communicate externally, or infer clinical content. A recommendation is an auditable
request for review, not an action.

The prior simulation found that review and fallback overhead could outweigh reduced manual work.
Shadow mode therefore tests detector quality and reviewer burden before any action-bearing pilot is
considered. All cases, snapshots, reviewers, decisions, labels, and outcomes are fictional.

## Online input contract

The operational referral events contain receipt timing and source context, but no credible structured
document or field-presence evidence before the manual completeness outcome. Using later
`missing_information_requested` events would leak the answer. Shadow mode therefore introduces a
separate `IncomingReferralSnapshot` stream without changing the operational dataset or its
fingerprint.

Each snapshot contains only:

| Field | Operational purpose |
| --- | --- |
| case and snapshot identifiers | correlation, idempotency, and provenance |
| `available_at` | the source watermark that controls detector visibility |
| source event and system | source traceability and stable ordering |
| referral source | permitted operational context; never a trigger alone |
| requested service line | selects explicit administrative form requirements only |
| fictional organisation identifier | source consistency without personal data |
| form and record versions | requirement selection and stale-update detection |
| referral-form presence | explicit structured intake completeness evidence |
| supporting-document presence | explicit structured intake completeness evidence |
| source acknowledgement | confirms structured source submission state |
| contact-route availability | administrative follow-up capability, not contact details |
| retry, synthetic, and schema markers | quality handling and safety validation |

Presence values are `present`, `absent`, `unknown`, `not_applicable`, or `unsupported`. Snapshots
contain no names, contact details, NHS numbers, addresses, diagnoses, symptoms, medical history,
treatment, urgency, protected attributes, or clinical free text.

The seeded intake generator adds delayed updates, corrections, unknown fields, stale versions, source
retries, and form-version differences. Its snapshot fingerprint is separate from the unchanged
operational dataset fingerprint. Hidden timing-aware labels are written to another artefact.

## Source availability and state

Replay order is:

1. `available_at`;
2. stable source-system priority; and
3. stable snapshot identifier.

Event time can provide historical context only after the source item is ingested. The runner never
sleeps; it advances logical time in deterministic order. `CaseStateProjector` starts empty, applies
only delivered snapshots, retains immutable revisions, detects stale versions and duplicate IDs, and
records source identifiers. Detector inputs are read-only Pydantic models that omit events, labels,
outcomes, reviews, and mutable operational records.

Replay supports a time window and a self-validating checkpoint. The checkpoint binds the run ID,
source fingerprint, detector and policy versions, cursor, case-state hashes, active recommendations,
audit root, and resumable state. Changed input or an incompatible version is rejected. A resumed run
converges to the same recommendations, detector results, final manifest, and audit root as an
uninterrupted run.

## Detector profiles

`strict` is the default. It recommends review only for an explicitly absent required supporting
document or source acknowledgement on the supported form. Unknown required evidence and unsupported
forms cause abstention. GP-practice membership alone never triggers.

`balanced` adds an absent supported administrative contact route as a trigger. `exploratory` also
turns some ambiguous structured evidence into recommendations. Exploratory mode is offline
evaluation-only and cannot be configured without hidden-label evaluation.

Every result is one of recommend, no recommendation, abstain, policy block, duplicate suppressed,
unchanged, revised, retracted, or detector failure. Rationales use deterministic templates attached
to structured reason codes. No LLM, predictive model, embedding, or clinical interpretation is used.

## Policy and abstention

`ShadowPolicy` allow-lists every detector input field and enforces supported schema/form versions,
structured administrative scope, human review, recommendation-only output, and complete provenance.
The prohibited boundary covers clinical fields, protected attributes, workflow mutation, external
communication, routing or service-line changes, rejection, approval, and employee ranking.

Policy statuses are permitted, permitted with warning, abstain required, blocked, and stop-condition
breach. A blocked result cannot create an active recommendation. Abstention is a valid output and is
reported separately; it is never silently counted as a negative prediction.

## Recommendation lifecycle and reviews

Recommendations have stable identities and versioned lifecycle events: created, updated, unchanged,
retracted, expired, reviewed, accepted, rejected, uncertain, superseded, and closed without review.
A correction can retract a concern before review. Duplicate source delivery, unchanged reasons, an
unresolved matching recommendation, and the suppression window prevent recommendation spam.
Historical lifecycle records are never deleted.

External fictional reviews are accepted as JSONL. Validation checks recommendation identity and
version, case identity, permitted reviewer role, unique decision, logical timestamp, explicit expiry
handling, synthetic marking, and sensitive-comment exclusions. Decisions include agree, disagree,
uncertain, already resolved, duplicate, insufficient context, policy concern, expired before review,
and not reviewed. No individual reviewer ranking is produced.

`benchmark_reviews` is isolated from deployable detector code. It may consult hidden labels to model
fictional agreement, error, uncertainty, delay, timeout, and already-resolved cases. The detector and
policy modules do not import the oracle or benchmark reviewer.

## Future-leakage threat model

The main threats are complete-timeline replay, using eventual missing-information events as features,
using labels or reviewer decisions during detection, event-time ordering ahead of ingestion, and
allowing later snapshot fields into an earlier projection. Controls are:

- different detector and label models;
- an oracle module outside the detector import graph;
- explicit `as_of` timestamps and runtime watermark assertions;
- source-availability ordering;
- audit records listing source references and accessed field names;
- no operational events in `DetectorInput`;
- tests that alter future snapshots, labels, and eventual outcomes without changing earlier results;
- critical tests confirming every accessed field existed by the cutoff.

Hidden labels answer: at the recommendation timestamp, did the fictional case genuinely require an
administrative completeness review under the applicable structured rules? A later missing-information
path alone does not make an earlier recommendation correct.

## Audit integrity

Every source receipt, ignored duplicate, state update, policy result, detector result, recommendation
lifecycle event, pause, completion, and evaluation has a typed append-only audit action. Each record
contains a sequence number, logical timestamp, actor, case/recommendation references, reason codes,
input/output references, detector and policy versions, canonical content hash, and previous hash.

The final record hash is the audit root. Verification detects modification, deletion, and reordering.
This is tamper-evident, not tamper-proof against a privileged file-system owner. Audit completeness
and a valid chain are mandatory promotion gates.

## Evaluation semantics

Quality reports preserve exact denominators and `null` unavailable values. They include precision,
recall, specificity, false-positive and false-negative rates, negative predictive value, F1,
evaluation coverage, recommendation coverage, abstention, detector failures, and permitted cohort
breakdowns above a minimum sample.

Burden separates all review time, false-positive time, useful time, and unresolved time. The GBP value
is a fictional administrative-cost proxy, not a saving. Latency uses logical timestamps for latest
required source to recommendation, case arrival to recommendation, recommendation to review, and
resolution before review. Program runtime is reported separately.

Reviewer metrics include agreement, rejection, uncertainty, already-resolved, policy concern,
override, completion, timeout, duration, and structured usefulness. Time-window outputs describe
observed period variation and never claim statistical drift.

## Stop conditions and promotion gates

Hard stop or pause conditions cover prohibited/clinical access, workflow mutation, missing policy
approval, audit failure, insufficient audit completeness, low precision after a minimum sample,
excess false-positive burden, reviewer rejection, recommendation volume, duplicates, detector
failure, unresolved review work, latency, unsupported input, and stale data.

Mandatory promotion gates cover safety, auditability, detector sample and precision, false-positive
burden, reviewer capacity, reviewer rejection, completion, and latency. Results are continue shadow
evaluation, revise detector, pause due to a stop condition, ready for a limited human-in-the-loop
pilot, or do not proceed. “Ready” would permit only design of a fictional, reversible, human-approved
pilot. It never approves production or autonomous action.

## Persistence and limitations

File-backed JSON/JSONL is authoritative for this milestone. PostgreSQL is used only as an optional,
read-only operational source whose generation fingerprint must match the manifest; intake snapshots
remain a separate file. No shadow table or migration is justified because file outputs already prove
append-only provenance without creating a write path near operational cases.

The prototype does not measure real benefit, realised cost, ROI, clinical performance, or production
reliability. Snapshot and reviewer behaviour are fictional assumptions. The detector deliberately
does less than the simulated intervention and cannot perform follow-on action.
