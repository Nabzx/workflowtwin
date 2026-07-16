# Baseline analysis benchmark

These local measurements are descriptive, not performance-test thresholds. They were recorded on
2026-07-16 with Python 3.12.12 on an arm64 macOS development laptop, fixed seed 42, the default
Northstar analysis configuration, and calculation version `1.0.0`.

Run them with:

```bash
uv run python scripts/benchmark_analysis.py
```

| Preset | Cases | Events | Analysis | Analysis + writes | Traced peak | JSON | Markdown | Case JSONL | Findings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tiny | 30 | 310 | 0.018s | 0.031s | 1.7 MiB | 141,673 B | 2,685 B | 253,940 B | 0 |
| demo | 1,000 | 10,085 | 0.424s | 0.587s | 24.9 MiB | 172,500 B | 3,243 B | 8,413,389 B | 5 |
| full | 10,000 | 101,413 | 6.202s | 7.729s | 239.7 MiB | 175,562 B | 3,381 B | 84,245,603 B | 6 |

`tracemalloc` materially slows the separately repeated memory-profile pass: 0.125s, 3.003s, and
34.371s respectively. The time columns above are the uninstrumented pass. Generation is intentionally
outside the timer. Writes include primary JSON, Markdown, and optional case JSONL; omitting JSONL
reduces time, disk, and memory pressure.

Stable fingerprints for this benchmark were:

- tiny: `f00105899ea35ae4dc9b2790b664dd2d19a312ade9b4fb0aa77af6170c5febf7`
- demo: `e7904a15a55a56c0d89dd37462dcf86064b751a155e57234a452a3f15aef9182`
- full: `5f85a132ca29bfddf704b7e97a4d75a1e500554fdfe52206389ac470571fbf78`

The demo and full benchmarks detected all four planted operational patterns. The demo also reported
elevated GP-practice rework. The full dataset additionally reported respiratory rework. Those are
expected overlapping effects of the planted incomplete-referral and scheduling-friction paths, not
false claims about a real provider.

For the demo, completion among terminal cases was 87.37%, median closed duration was 219.96 hours,
56 cases contained ingestion delays over 24 hours, 33 had out-of-order ingestion, and no case was
excluded entirely. For the full dataset the corresponding values were 86.49%, 219.86 hours, 615,
370, and zero. Processing effort and waiting remain explicitly estimated; the benchmark does not
measure clinical outcomes.
