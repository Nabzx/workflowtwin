# Shadow-mode benchmark

## Fixed inputs

The benchmark uses the existing seed-42 fictional Northstar datasets and the unchanged selected
opportunity `opportunity-7def8c82e8b589e5`. Intake snapshots and timing-aware labels are generated in
separate deterministic streams. The first run after implementation was retained; detector rules were
not tuned after observing results. A promotion-aggregation defect that allowed a pause-level capacity
breach to coexist with a ready result was corrected without changing detector output.

## 1,000-case profile comparison

| Metric | Strict | Balanced | Exploratory |
| --- | ---: | ---: | ---: |
| Cases / source snapshots | 1,000 / 1,092 | 1,000 / 1,092 | 1,000 / 1,092 |
| Eligible cases | 869 | 869 | 869 |
| Recommendations | 224 | 243 | 310 |
| Coverage | 22.40% | 24.30% | 31.00% |
| Abstentions | 200 | 198 | 131 |
| True positives | 208 | 210 | 223 |
| False positives | 16 | 33 | 87 |
| False negatives | 42 | 40 | 40 |
| Precision | 92.86% | 86.42% | 71.94% |
| Recall | 83.20% | 84.00% | 84.79% |
| False-positive rate | 2.91% | 5.98% | 14.36% |
| False-positive review hours | 1.153 | 2.683 | 6.433 |
| Reviewer agreement | 74.11% | 67.08% | 58.39% |
| Reviewer rejection | 5.80% | 13.17% | 25.16% |
| Revisions / retractions | 0 / 47 | 3 / 44 | 8 / 57 |
| Expiries / duplicates suppressed | 176 / 0 | 198 / 1 | 252 / 1 |
| Audit records | 4,800 | 4,842 | 4,981 |
| Audit completeness / policy compliance | 100% / 100% | 100% / 100% | 100% / 100% |
| Source-to-recommendation P50 / P95 | 0 / 0 logical min | 0 / 0 | 0 / 0 |
| Runtime | 0.396 s | 0.395 s | 0.460 s |
| Assessment | pause | pause | pause |

Strict passes precision, false-positive burden, reviewer rejection, review completion, latency,
safety, policy, and audit gates. It fails the configured maximum recommendation rate of 20% because
coverage is 22.4%. Balanced also fails precision and false-positive burden. Exploratory additionally
fails reviewer rejection and remains evaluation-only.

Strict precision across logical seven-day windows ranged from 75% to 100%, with several windows below
the minimum cohort size. This is observed performance variation, not a formal drift finding, and
requires further monitoring.

Stable evaluation fingerprints:

- strict: `74da6704f109b3229a3fb232ab05cc69c609755ccb507a375099ab6f8ade4e18`
- balanced: `f241931459267a2b352b915ce9d6f81c2b8e889708352d8e073c191741cdfc2d`
- exploratory: `e171368f29700b66a93a9a445bd30d66c42549bdab86cefe18eab4c3cd9feeee`

The strict audit root is
`16614559ef7571de4d02f52638bd8f0062ac16577dabfc4b54198f591c2de7b6`.

## 10,000-case strict benchmark

| Measure | Result |
| --- | ---: |
| Cases / source snapshots | 10,000 / 10,996 |
| Eligible cases | 8,812 |
| Recommendations / reviews | 2,072 / 2,072 |
| Coverage / abstention rate | 20.72% / 20.87% |
| True positives / false positives / false negatives | 1,952 / 120 / 557 |
| Precision / recall | 94.21% / 77.80% |
| False-positive rate | 2.22% |
| False-positive review hours | 8.684 |
| Reviewer agreement / rejection | 71.77% / 4.68% |
| Retractions / expiries | 570 / 1,502 |
| Audit records | 47,925 |
| Audit completeness / policy violations | 100% / 0 |
| Source-to-recommendation P50 / P95 | 0 / 0 logical minutes |
| Detector replay runtime | 14.057 s |
| Replay throughput | 782.3 snapshots/s |
| Approximate peak process memory | 498.7 MiB |
| Complete checkpoint size | 1,060,604 bytes |
| Evaluation, report, visualisation size | 46,046 bytes |
| Promotion assessment | `pause_due_to_stop_condition` |

The sole breached strict stop condition is recommendation volume: 20.72% is above the 20% capacity
threshold. All safety, audit, precision, false-positive burden, rejection, completion, and latency
gates pass. The result therefore supports revising eligibility or staged review capacity, not a pilot.

Full evaluation fingerprint:
`a9c770fa1abd07a0a0a48b77a06174515544bc05f90e63d20aca393d383a08af`.

Full audit root:
`91591d25d95fa2d3626ddf81a1b7f15dd3e96433d2a5240eab071a43ad8acc23`.

## Reproduction

```bash
uv run python scripts/benchmark_shadow_mode.py --force

uv run python scripts/benchmark_shadow_mode.py \
  --dataset artifacts/generation/full-dataset.json \
  --opportunity-analysis artifacts/opportunities/full-opportunities.json \
  --simulation-analysis artifacts/simulation/demo-central.json \
  --strict-only \
  --output-dir artifacts/shadow/full \
  --force
```

Runtime values are observations from one local run and are not test thresholds. Files under
`artifacts/shadow/` are reproducible and ignored by Git.
