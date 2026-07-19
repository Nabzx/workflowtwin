"""CLI adapter for the supported FastAPI application."""

from __future__ import annotations

import argparse

import uvicorn


def configure_serve_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("serve", help="serve the fictional local pilot API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")


def run_serve(args: argparse.Namespace) -> int:
    uvicorn.run(
        "workflowtwin.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0
