# Shadow detector evolution

> Northstar Clinics, every case, system, reviewer, capacity value, and result is fictional. No
> production deployment or real operational impact occurred.

The complete pre-cleanup implementation is preserved in Git history and by the annotated tag
`shadow-evaluation-complete`, which points to commit `d72d610`. Compact machine-readable goldens in
`tests/fixtures/experiments/` preserve the published fingerprints, representative stable identifiers,
headline metrics, and assessments without duplicating the historical runtime on the supported branch.

## Comparison

| Experiment | Intake | Design | Precision | Recall | Detector coverage | Surfaced coverage | Assessment |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| strict-v1 | V1 | immediate explicit absence | 93.02% | 62.11% | 20.48% | not comparable | `do_not_promote` |
| strict-v2 | V1 | 120-minute confirmation | 93.12% | 51.19% | 16.86% | not comparable | `do_not_promote` |
| strict-v3 | V2 | explicit applicability and evidence stability | 93.16% | 78.39% | 25.83% | 14.87% | `strict_v3_validation_failed` |

## Strict-v1

Strict-v1 recommended an administrative completeness review immediately when its V1 projection
reported an absent supporting document. Precision was strong, but its original shadow study paused
because recommendation volume exceeded the registered capacity threshold. On the later immutable
10,000-case comparison holdout it produced 2,048 positives, 9.53 fictional false-positive review
hours, 93.02% precision, and 62.11% recall.

Configuration fingerprint:
`d77c462abd139ab5460579043c2adf4af3b172c87c0d2b7c2d26af4f175ea0ba`.

## Strict-v2

Strict-v2 retained explicit V1 absence but waited 120 logical minutes for a correcting source update.
It reduced detector positives to 1,686 and fictional false-positive review time to 7.73 hours on the
same holdout. Precision remained 93.12%, while recall fell materially to 51.19%. It failed its 72%
recall gate and remains `do_not_promote`.

Detector fingerprint:
`7ecc87d12fb5fdc30413acec9787afc571ae2caf6a0b42b054b040708cfc9b3b`.

The holdout comparison fingerprint is
`b193f998ffb9ce885d13c3878d1ee66b1f32a8dd8308224c911655673abed578`.
Its registry was opened once and is immutable. A capacity-reporting denominator defect was corrected
afterward: detector quality counts, precision, recall, and the promotion result did not change.

## Source-contract V2

Strict-v2's recall failure prompted source observability analysis instead of further threshold tuning.
V2 distinguished explicit absence from unknown, added applicability, producer and availability time,
requirements versions, freshness, conflicts, warnings, manual-review state, supersession, and full
administrative provenance. Generator truth stayed separate from detector input. Clinical fields were
prohibited.

Source-contract fingerprint:
`2e1518711bb463056f004194642580e98b454f9e717f6f46a11ea230cd463cc8`.
Requirements fingerprint:
`45055eaf3cbdc0a65cab7d81c39dac103a75c16581ea131c946944897590d6d5`.

## Strict-v3

Strict-v3 used V2 as-of-time evidence. It recommended on trusted explicit administrative absence or
verification-required state; abstained on unknown, stale, conflicting, unsupported, or mismatched
state; observed existing warnings/manual review without duplication; and retracted after superseding
resolution.

Development C passed. Development D exceeded the 25% detector-positive cap at 25.40%. The frozen
3,000-case Validation V3 run produced 775 positives, 478 active recommendations, and 446 surfaced
recommendations. Precision was 93.16%, recall was 78.39%, and recall reached 100% of the measured
observable ceiling. Safety, policy, audit, false-positive burden, latency, and surfaced coverage gates
passed. Raw detector-positive coverage was 25.83%, so the pre-registered protocol returned
`strict_v3_validation_failed`.

Detector fingerprint:
`1e8c75cfea53f1dc449250d5a53974b7fef4a633bd5cd2110f133fc209923bda`.
Evaluation fingerprint:
`f39aa5f420567bee94c320c0648a5e7a1ac433885fc6dbd76d6d0521609cd128`.

Holdout V3 was never opened. No lock, registry, labels, or result exists, and it must remain unopened.
Detector-positive coverage counts all detected signals; surfaced coverage counts the smaller workload
actually shown to fictional reviewers. Neither denominator may silently replace the other.

## Product decision

Further detector tuning stopped. The supported product detector is an adapter over the unchanged
strict-v3 logic, exposed as `completeness-review-detector-v1` with its strict-v3 lineage retained.
A separate fictional pilot policy measures surfaced reviewer workload and requires a human decision
before creating a reversible mock administrative task. This new policy does not rewrite or pass the
historical strict-v3 protocol, does not open its holdout, and authorises no production use.
