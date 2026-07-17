# Opportunity identification benchmark

This local benchmark used the fixed 1,000-case Northstar demo artifacts, seed 42, the version 1
baseline and process analyses, and the nine-session fictional research pack. Results are synthetic
engineering checks, not evidence about a real provider, staff, patients, or clinical outcomes.

Run on 2026-07-17 with:

```bash
uv run python scripts/benchmark_opportunities.py
```

| Measure | Result |
| --- | ---: |
| Evidence records | 683 |
| Fictional research sessions | 9 |
| Raw / deduplicated candidates | 7 / 6 |
| Controlled prototype / further discovery / blocked | 1 / 5 / 0 |
| Expected synthetic patterns detected | 4 / 4 |
| Analysis time | 0.079 s |
| Analysis plus artifact writing | 0.100 s |
| Python traced peak memory | 2.5 MiB |
| Full analysis JSON | 612,470 bytes |
| Stakeholder Markdown | 8,893 bytes |
| Portfolio JSON | 3,064 bytes |
| Evidence-network JSON | 46,120 bytes |

Runtime and memory are single local observations, not service-level objectives. The benchmark loads
existing aggregate artifacts before timing, runs opportunity analysis once under `tracemalloc`, and
writes outputs to a temporary directory. The fingerprint is deterministic for the input artifacts,
analysis identifier, versions, and configuration; wall-clock analysis time is excluded.
