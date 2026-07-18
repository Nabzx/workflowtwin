"""Benchmark source-contract validation and historical observability analysis."""

import argparse
import time
import tracemalloc
from pathlib import Path

from workflowtwin.cli.main import main


def entrypoint() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    force = ["--force"] if args.force else []
    tracemalloc.start()
    started = time.perf_counter()
    status = main(["source-contract-validate", *force])
    if status == 0:
        status = main(["shadow-analyse-misses", *force])
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - started
    output = Path("artifacts/source-contract/missed-positive-analysis.json")
    print(f"Runtime seconds: {elapsed:.3f}")
    print(f"Peak traced memory MiB: {peak / 1024 / 1024:.2f}")
    if output.exists():
        print(f"Analysis bytes: {output.stat().st_size}")
    return status


if __name__ == "__main__":
    raise SystemExit(entrypoint())
