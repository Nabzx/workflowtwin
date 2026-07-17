# Process-mining benchmark

All measurements use fictional Northstar Clinics administrative data generated with seed `42` on
2026-07-17. They are reproducibility evidence for this implementation, not clinical evidence or
performance guarantees. Generated datasets and reports remain ignored under `artifacts/`.

## Fixed 1,000-case demo

| Measure | Result |
| --- | ---: |
| Cases / events | 1,000 / 10,085 |
| Activities / transitions / variants | 17 / 23 / 57 |
| Top 1 / 5 / 10 variant coverage | 36.3% / 67.0% / 80.2% |
| Mean / median / maximum activities per case | 10.085 / 9 / 19 |
| Loop / rework / handoff case rate | 40.8% / 51.2% / 93.1% |
| Variant entropy | 3.697 bits |
| Strict fully conforming | 36.3% |
| Governed fully conforming | 87.1% |
| Candidate bottlenecks | 19 |
| Planted patterns detected | 4 / 4 |
| Process fingerprint | `eadb8843d6ca11010de7233df990dcccf41f0ce82cb2ec1839db40c83eb62497` |

The most common variant is the nine-step straight-through completion path. The most frequent loop
is `Scheduling started -> Scheduling failed -> Scheduling started` (167 outward occurrences across
132 cases), followed by 38 consecutive completeness-check repeats. The slowest observed material
transitions include scheduling to patient non-response (261.78 median elapsed hours), missing
information to non-response (207.48), scheduling to booking (144.34), failed scheduling to retry
(75.77), and information request to response (36.28). These are elapsed delays, not active work.

Governed deviations are scheduling retry (132), excessive loop (49), missing terminal event (42),
and unexpected order (30). Process candidates independently surfaced GP-practice information
rework, Neurology assignment delay, Respiratory scheduling retries, and Dermatology reassignment.
All five baseline findings were supported. Additional candidates include long non-response waits,
slow general scheduling, and rare long-duration variants; these may be overlapping planted effects
or ordinary synthetic variation and do not establish new causes.

JSON analysis, graph JSON, Markdown, and 1,000-line case JSONL were produced. Their sizes were
321,123 bytes, 84,928 bytes, 6,958 bytes, and 3,176,625 bytes. Graphviz `dot` was unavailable, so
all six optional SVG attempts returned warnings without invalidating analysis.

The same demo was persisted in PostgreSQL, loaded by completed generation run with explicit
database ordering, and analysed through `--from-database`. File and database inputs both produced
process fingerprint `eadb8843d6ca11010de7233df990dcccf41f0ce82cb2ec1839db40c83eb62497`.

## Fixed 10,000-case benchmark

| Measure | Result |
| --- | ---: |
| Cases / events | 10,000 / 101,413 |
| Wall time, full CLI process analysis | 19.79 seconds |
| Strict / governed replay time | 2.771 / 0.699 seconds |
| Combined replay time | 3.470 seconds |
| Approximate peak RSS, load plus both replays | 623.2 MiB |
| Activities / transitions / variants | 17 / 23 / 100 |
| Top 1 / 5 / 10 variant coverage | 34.09% / 65.16% / 79.11% |
| Strict / governed fully conforming | 34.09% / 85.96% |
| Candidate bottlenecks | 27 |
| Planted patterns detected | 4 / 4 |
| JSON / graph / Markdown size | 486,903 / 135,110 / 7,106 bytes |
| Process fingerprint | `f9f75f86cb0f2221606426e89647a23733567fe88d27745ab6eaeedfab60d5cd` |

The full run supported all six baseline findings. Its most frequent scheduling loop had 1,864
outward occurrences across 1,468 cases. Governed deviations were scheduling retry (1,468),
excessive loop (540), missing terminal event (467), and unexpected order (326). The benchmark is
comfortably in-memory at this scale, but the peak measurement includes dataset loading and replay,
not a profiler-derived per-stage allocation breakdown.

## Reproduce

```bash
uv run workflowtwin generate --preset demo --seed 42 --run-id northstar-demo-42 \
  --dataset-output artifacts/generation/demo-dataset.json
uv run workflowtwin analyze --dataset artifacts/generation/demo-dataset.json \
  --analysis-output artifacts/analysis/demo-analysis.json \
  --report-output artifacts/analysis/demo-report.md
uv run workflowtwin process-mine --dataset artifacts/generation/demo-dataset.json \
  --baseline-analysis artifacts/analysis/demo-analysis.json \
  --analysis-output artifacts/process/demo-process-analysis.json \
  --report-output artifacts/process/demo-process-report.md \
  --graph-output artifacts/process/demo-process-graph.json
```
