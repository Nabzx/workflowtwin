# Fictional pilot benchmark

Measured locally on 2026-07-19 using Python 3.12 on a developer laptop. Timings are indicative and
have no pass/fail assertion. Northstar and every dataset and result are fictional.

| Operation | Fixed workload | Approximate wall time |
|---|---:|---:|
| Fast demo command | 120 cases, supported V2 detector, 12 surfaced drafts | 1.3 s |
| Full demo command | 1,000-case analysis plus 120-case pilot seed | 8.4 s |
| API application construction | deterministic local pilot state | 102 ms |
| Recommendation list | 12 records, 50-request mean | 0.33 ms |
| Review response | one local rejection | 0.74 ms |
| Approved draft action | one local mock task | 0.80 ms |
| Audit verification | 34 records, 1,000-run mean | 0.69 ms |
| Last full suite with coverage | 195 passed, 16 PostgreSQL-only skipped | 139.4 s |

The pilot seed reports 96.6% precision, 80.0% recall, 24.2% detector-positive coverage, 10.0%
surfaced coverage, 12 maximum queued drafts, 12 review minutes, two local task commits, one verified
rollback, zero messages, and zero operational event mutations. All 20 fictional pilot gates pass.

The full analytical demo records stable fingerprints for the operational dataset, baseline analysis,
process reconstruction, opportunity portfolio, counterfactual simulation, supported detector, pilot
policy, audit chain, and final pilot run.

Peak resident memory during the isolated API measurement was approximately 64 MiB. PM4Py and Python
allocator behavior vary by platform, and macOS did not expose command-level memory through
`/usr/bin/time` in the restricted shell. The benchmark is intended to reveal order of magnitude,
not claim production capacity; refresh it after frontend or deployment changes.
