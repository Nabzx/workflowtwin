"""Run the pre-registered refinement benchmark, with opt-in holdout opening."""

import argparse

from workflowtwin.cli.main import main


def entrypoint() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--include-holdout", action="store_true")
    args = parser.parse_args()
    command = ["shadow-refine"]
    if args.force:
        command.append("--force")
    status = main(command)
    if status == 0 and args.include_holdout:
        status = main(["shadow-holdout"])
    return status


if __name__ == "__main__":
    raise SystemExit(entrypoint())
