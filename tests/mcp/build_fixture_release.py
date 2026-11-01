#!/usr/bin/env python3
"""Build a hosted MCP release from the synthetic mini-library, for tests.

Copies tests/fixtures/mini-library to a temporary folder, stamps it with the
synthetic approval metadata from tests/approved_fixture.py (the same contract
the real Custodian release must pass), adds one DOHA manifest row marked
answer_eligible: false so the exclusion path has something to exclude, and
runs scripts/hosted_release.py against it with --skip-checks (the test suite
is what calls this, so running the suite from inside it would recurse).

Nothing here touches mcp/release/ or mcp/wrangler.jsonc: the build goes to
the folder given on the command line and the config is a temporary copy.

Usage: python tests/mcp/build_fixture_release.py <out_dir>
Exit: hosted_release.py's exit code (0 built, 2 refused).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
import approved_fixture  # noqa: E402

MINI = ROOT / "tests" / "fixtures" / "mini-library"
HOSTED = ROOT / "scripts" / "hosted_release.py"
CONFIG = ROOT / "mcp" / "wrangler.jsonc"

EXCLUDED_ROW = {
    "document_id": "test-90-00009.h1_denied_g",
    "case_stem": "90-00009.h1_denied_g",
    "current_group": "POST_SEAD_4",
    "sead4_era": "post_sead4",
    "answer_eligible": False,
    "robot_text_path": "ROBOT_READABLE_DIRECTORY/TEXT/X/90-00009.h1_denied_g.txt",
}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="aia-fixture-") as td:
        lib = Path(td) / "library"
        shutil.copytree(MINI, lib)
        approved_fixture.prepare(lib)
        paths = lib / "ROBOT_READABLE_DIRECTORY" / "MANIFESTS" / "DOHA_CURRENT_PATHS.jsonl"
        with paths.open("a", encoding="utf-8") as f:
            f.write(json.dumps(EXCLUDED_ROW) + "\n")
        config = Path(td) / "wrangler.jsonc"
        shutil.copy(CONFIG, config)
        r = subprocess.run(
            [sys.executable, str(HOSTED), "--library", str(lib), "--out", str(out), "--config", str(config), "--skip-checks"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        return r.returncode


if __name__ == "__main__":
    sys.exit(main())
