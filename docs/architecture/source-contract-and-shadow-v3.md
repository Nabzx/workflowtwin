# Missed-positive source contracts and strict-v3

> Northstar Clinics, its systems, forms, cases, staff signals, and all results are fictional. This
> milestone evaluates administrative recommendations only. It contains no clinical information,
> LLM, learned model, production integration, workflow mutation, or realised impact claim.

## Decision summary

`strict-v2` preserved precision but reduced recall from 62.11% to 51.19% on its immutable prior
holdout. Further tuning against that result was rejected. WorkflowTwin instead asked which misses
were observable from the source state available before a useful administrative recommendation.

The source-only replay found meaningful recoverable recall, so a new `strict-v3` was justified and
pre-registered. Validation V3 then failed one mandatory capacity gate. The evidence chain stopped:

```text
Strict-v2 recall failure
-> missed-positive taxonomy
-> source observability analysis
-> explicit V2 source contract
-> pre-registered strict-v3
-> Validation V3 coverage failure
-> holdout V3 remains unopened
```

The final assessment is `strict_v3_validation_failed`. This is neither deployment approval nor a
claim that V2 source improvements would work in a real provider.

## Miss taxonomy and observability

Every evaluable hidden positive receives one primary cause, optional secondary causes, source
references, an availability timeline, the latest useful decision time, recoverability flags, and
policy/latency/false-positive implications. Stable categories cover unavailable or late evidence,
unknown/absent ambiguity, unknown applicability, unsupported forms, stale or conflicting state,
confirmation delay, policy abstention, review already underway, capacity withholding, detector-rule
misses, and label uncertainty.

Observability statuses distinguish detected, missed, partial, late, unobservable, policy-prohibited,
and non-evaluable cases. Labels are joined only after V2 publication and detector output are frozen.
The ceiling is therefore an evaluation statistic, never a runtime feature.

On historical validation seed 303, the old V1 detector missed 345 of 901 positives and `strict-v2`
missed 440. Its misses comprised 164 unavailable/inaccurate source representations, 118 unsupported
forms, 95 confirmation-window misses, and 63 unknown/absent ambiguities. There were 238 portal, 130
secure-email, and 72 manual-entry misses; 294 had no later source evidence, 132 had an update within
120 minutes, and 14 updated later.

V2 made 728 of the 901 positives observable and usable in time, giving an 80.80% source-contract
ceiling. Residual categories were 77 unavailable, 40 unsupported form, 23 unknown, 19 stale, and 14
conflicting. The ceiling by source was 82.00% manual entry, 81.46% referral portal, and 78.69% secure
email. By form it was 87.21% `NS-INTAKE-1`, 83.40% `NS-INTAKE-2`, and 0% unknown. Capacity is reported
separately and cannot alter these ceilings.

## V2 contract

`IncomingReferralSnapshotV2` coexists with V1. Its field observations use nine explicit states:

| State | Runtime meaning |
| --- | --- |
| `present` | explicit resolved administrative evidence |
| `absent` | explicit absence; recommendation may be allowed under the requirements contract |
| `unknown` | producer cannot state presence; abstain |
| `not_applicable` | requirement explicitly does not apply; do not recommend |
| `pending_source_update` | wait for the pre-registered confirmation period |
| `unsupported` | producer cannot represent the field; abstain |
| `stale` | freshness contract failed; abstain |
| `conflicting` | sources or updates disagree; abstain and review |
| `verification_required` | producer explicitly requests administrative verification |

Snapshots carry source event and availability times, record and schema versions, form and
requirements versions, explicit applicability, producer, warning codes, manual-review state,
freshness, conflict status, update type, supersession, and provenance. Read-only V1/V2 compatibility
views preserve V1 `unknown` exactly; old snapshots never inherit V2 absence semantics.

The machine-readable requirements contract defines administrative fields, documents,
acknowledgements, routing contacts, explicit administrative conditions, source support/exceptions,
unsupported combinations, effective periods, version, provenance, and a fictional declaration.
Clinical conditions and prohibited identifiers are rejected.

## Source quality and precedence

The validation replay published 3,291 V2 snapshots. Supported-form rate was 95.90%, applicability
coverage 96.92%, requirements-version agreement 98.63%, usable-input coverage 90.61%, stale rate
2.67%, and conflict rate 1.61%. Provenance completeness and supersession integrity were 100%.

The versioned precedence order is referral portal, secure email, then manual entry, subject to fresh
state and monotonic versions. A conflict never uses the hidden outcome label to choose a winner;
equal-version disagreement requires abstention and manual verification. Contradiction analysis also
flags missing warnings on not-applicable fields, non-monotonic supersession, warnings persisting after
resolution, and producer disagreement. Generator truth, published state, availability, detector
input, and evaluation labels are separate artifacts.

## Strict-v3 protocol

The protocol registered Development C (seed 505, 1,000 cases), Development D (606, 1,000),
Validation V3 (707, 3,000), and Holdout V3 (808, 10,000) before evaluation. It locks detector,
policy, source-contract, requirements-contract, and capacity fingerprints. Precision must be at least
90%, recall at least 72%, ceiling-relative recall at least 88%, detector coverage at most 25%,
surfaced coverage at most 20%, p95 latency at most 30 minutes, and fictional false-positive review
time at most 0.25 hours per 100 cases. Safety, policy, audit, source quality, and cohort gates are
mandatory.

The detector uses only V2 snapshots available as of each decision. Trusted explicit absence and
verification-required evidence can recommend immediately; pending state waits 180 minutes; unknown,
stale, conflicting, unsupported, and mismatched contracts abstain. Existing source warnings and
manual review become observe-only. Retries are suppressed and superseding present evidence retracts.
Every result is recommendation-only and append-only audit records form a verified hash chain.

## Evaluation result

| Split | Precision | Recall | Ceiling | Relative | Detector coverage | Surfaced | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Development C | 93.52% | 77.00% | 77.00% | 100% | 24.70% | 15.20% | gates passed |
| Development D | 95.28% | 75.86% | 75.86% | 100% | 25.40% | 14.30% | coverage failed |
| Validation V3 | 93.16% | 78.39% | 78.39% | 100% | 25.83% | 14.87% | validation failed |

Validation processed 3,000 cases and 3,302 snapshots: 921 hidden positives, 775 detector positives,
478 active recommendations, 446 surfaced/reviewed recommendations, 722 true positives, 53 false
positives, and 199 false negatives. Specificity was 97.45%, false-positive rate 2.55%, fictional
false-positive review burden 3.53 hours, mean recommendation latency 0.25 minutes, and p95 latency
zero. There were 351 abstentions, including 263 contract-related abstentions, and a 25.16% retraction
rate. All source, safety, audit, policy, latency, precision, recall, burden, and surfaced-capacity gates
passed; detector-positive coverage alone failed.

Controlled split comparisons include V1 and V2, but prior V1/V2 holdout figures are labelled as a
different population. No exact cross-holdout causal claim is made.

## Holdout isolation and limitations

Validation failure prevented creation of `strict-v3-lock.json`. The holdout command refuses to run
without that lock. No V3 holdout dataset, labels, registry, evaluation, or report exists, and the
registered evaluation count remains zero. The prior holdout registry and its V1/V2 artifacts remain
immutable.

These benchmarks are deterministic synthetic administrative exercises. Reviewer time, capacity,
quality, and outcomes are fictional. A 100% ceiling-relative recall result reflects this explicit
contract and oracle, not universal detectability. The next milestone should investigate producer-side
unavailable, ambiguous, stale, conflicting, and unsupported states and the operational meaning of the
coverage cap. It must stay in shadow mode, must not tune `strict-v3`, and must not open holdout V3.
