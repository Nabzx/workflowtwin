# Intervention simulation benchmark

All results below are fictional counterfactual engineering measurements. They are not production
performance, realised savings, ROI, staff evaluation, patient benefit, or clinical evidence.

## Fixed 1,000-case scenarios

The selected opportunity is GP-practice intake completeness validation. Baseline eligibility is 422
GP-practice cases. Manual-touch and first-check differences are per eligible case; burden includes
review, fallback, and recovery touch assumptions.

| Scenario | Affected | Reviewed | Fallbacks | Failures | Manual-touch difference | First-check hours | Control hours | Net modelled hours | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Conservative | 28 | 88 | 43 | 17 | -0.095 | -0.626 | 9.917 | -6.583 | Revise design |
| Central | 67 | 110 | 23 | 11 | -0.284 | -2.364 | 10.375 | -0.375 | Proceed only with controls |
| Optimistic | 125 | 158 | 12 | 2 | -0.566 | -5.045 | 13.833 | +6.083 | Proceed only with controls |
| Adverse | 28 | 101 | 89 | 61 | -0.095 | -0.464 | 13.333 | -10.000 | Revise design |

All scenarios retain 57 variants and an 87.1% governed fully conforming rate because the
intervention changes timing and manual markers while preserving the administrative activity
sequence. Central sensitivity finds positive net burden only at the tested 2% false-positive point
or the tested 85% effectiveness point. No tested fallback rate from 5% to 45% is positive. These are
coarse modelled boundaries, not production guarantees.

## 10,000-case central benchmark

Run with:

```bash
uv run python scripts/benchmark_simulation.py
```

| Measure | Result |
| --- | ---: |
| Source cases / events | 10,000 / 101,413 |
| Eligible / affected cases | 4,337 / 674 |
| Counterfactual events | 101,413 |
| Fallbacks / simulated failures | 283 / 131 |
| Counterfactual construction | 18.705 s |
| Baseline re-analysis | 21.188 s |
| Process re-analysis | 49.888 s |
| Total measured pipeline | 89.802 s |
| Python traced peak memory | 879.0 MiB |
| Manifest JSON | 3,611 bytes |
| Optional case JSONL | 26,092,980 bytes |
| Manual-touch difference per eligible case | -0.277 |
| First-check difference | -2.699 hours |
| Control overhead | 109.333 hours |
| Net modelled burden difference | -9.167 hours |
| Decision | Revise intervention design |

The benchmark fingerprint is
`7be792b148b09bb364211f6f3739553536b6413e541406f999ce2d0fa372a4e6`.
Times and memory are one local observation with no machine-dependent assertion. The 26 MB optional
case output is ignored by Git and supports audit/debug workflows rather than the primary report.
