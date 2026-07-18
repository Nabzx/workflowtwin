"""Benchmark strict-v3 development and validation without bypassing holdout gates."""

import argparse
import time
import tracemalloc
from pathlib import Path

from workflowtwin.cli.main import main


def entrypoint() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--include-holdout", action="store_true")
    args = parser.parse_args()
    force = ["--force"] if args.force else []
    tracemalloc.start()
    started = time.perf_counter()
    status = main(["shadow-v3-develop", *force])
    if status == 0:
        status = main(["shadow-v3-validate", *force])
    if status == 0 and args.include_holdout:
        status = main(["shadow-v3-holdout"])
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"Runtime seconds: {time.perf_counter() - started:.3f}")
    print(f"Peak traced memory MiB: {peak / 1024 / 1024:.2f}")
    for name in ("development.json", "validation.json", "holdout.json"):
        path = Path("artifacts/shadow-v3") / name
        if path.exists():
            print(f"{name} bytes: {path.stat().st_size}")
    return status


if __name__ == "__main__":
    raise SystemExit(entrypoint())
