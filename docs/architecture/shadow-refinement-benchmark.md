# Shadow refinement benchmark

All results describe deterministic synthetic administrative records for the fictional Northstar
Clinics. Review time and capacity are assumptions. Results say nothing about a real provider or
clinical outcomes and authorise no workflow action.

## Registered comparison

| Split | Cases | Version | Positives | Precision | Recall | FP review hours | Added latency |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Development A | 1,000 | strict-v1 | 229 | 93.36% | 67.30% | 1.00 | 0 min |
| Development A | 1,000 | strict-v2 | 188 | 93.09% | 55.03% | 0.87 | 120 min |
| Development B | 1,000 | strict-v1 | 195 | 93.85% | 61.20% | 0.80 | 0 min |
| Development B | 1,000 | strict-v2 | 161 | 93.17% | 50.17% | 0.73 | 120 min |
| Validation | 3,000 | strict-v1 | 594 | 93.60% | 61.70% | 2.53 | 0 min |
| Validation | 3,000 | strict-v2 | 493 | 93.51% | 51.17% | 2.13 | 120 min |
| Holdout | 10,000 | strict-v1 | 2,048 | 93.02% | 62.11% | 9.53 | 0 min |
| Holdout | 10,000 | strict-v2 | 1,686 | 93.12% | 51.19% | 7.73 | 120 min |

Detector fingerprint `7ecc87d12fb5fdc30413acec9787afc571ae2caf6a0b42b054b040708cfc9b3b`
was fixed before holdout seed 404 was opened. The registry records one completed evaluation.

## Diagnostics

The strict-v1 development diagnostic found transient field arrival/source delay and misleading
structured absence as false-positive causes, plus recommendations corrected before the fictional
review window. `strict-v2` resolved 101 validation and 362 holdout concerns during confirmation.
The remaining holdout false positives were 116 misleading explicit absences. Missed positives are
retained individually with the exclusion rule, fictional consequence, and excessive-narrowing flag.

Validation cohort reporting covers source system, form version, referral source, and service line.
Unsupported and unknown forms have zero recall by design. Referral-source precision ranged from
85.23% to 97.05%, while recall ranged from 44.64% to 56.39%. These are guardrails and must not be
used as routing or risk proxies. Twenty-seven holdout chronological windows are retained.

## Sensitivity and capacity

On validation, report-only confirmation windows of 60, 120, and 180 minutes produced recall of
55.49%, 51.17%, and 45.84% respectively. Precision remained around 93.5% while burden decreased.
This monotonic trade-off supports the decision not to tune the window after seeing holdout results.

Capacity profiles run after detection and preserve every positive. Under the standard fictional
profile, surfaced coverage was 17.90%, 14.80%, and 15.17% across development A, development B, and
validation. The original holdout artifact used 2,048 signal-bearing cases as its capacity coverage
denominator. A transparent correction records the proper 10,000-case denominator: strict-v2
detector-positive coverage is 16.86%, with 7.18% surfaced under the standard profile. Detector
precision, recall, counts, and the promotion decision were unaffected.

## Decision

`strict-v2` passes precision, false-positive burden, policy, and audit gates but fails the registered
72% recall gate on every split. Capacity queues also defer work under constrained profiles. The
decision is **do not promote**. Continue recommendation-only shadow analysis; do not build an
action-bearing automation around either detector version.
