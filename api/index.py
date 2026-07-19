"""Vercel ASGI entry point for the unified fictional demonstration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workflowtwin.main import app

__all__ = ["app"]
