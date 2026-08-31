#!/usr/bin/env python3
"""Stable repository entry point for the local product shell."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adverse_app.cli import main

raise SystemExit(main())

