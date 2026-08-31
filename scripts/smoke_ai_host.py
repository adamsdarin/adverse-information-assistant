#!/usr/bin/env python3
"""Synthetic smoke test for the local Codex browser adapter."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adverse_app import core
from adverse_app.codex_host import turn

session = ROOT / "output" / "ai-smoke-session.json"
core.start(session, "high", force=True)
response = turn(session, "Begin the session using this synthetic test checkpoint. Ask only the next question.")
print(response)
