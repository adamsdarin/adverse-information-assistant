#!/usr/bin/env python3
"""Locate and read the DCSA Library. Companion to corpus_paths.py.

Two external things this tool depends on, and they are NOT the same:

  corpus/   — the maintainer's authored analysis (checklists, reporting
              tables, form maps). Small. SHIPS IN THE REPO.
  Library   — the DCSA Library: source documents, DOHA decisions, and
              retrieval indexes. Large. DOWNLOADED SEPARATELY by the user
              and placed wherever they like.

Resolution order (first hit wins):
  1. An explicit --library PATH
  2. The AIA_LIBRARY environment variable
  3. .library-location.json, written by `check_library.py <path> --remember`
  4. A few conventional locations under the user's home

The library declares its own root: any folder containing
START_HERE_FOR_ROBOTS.json is a library root, and every path inside that
file is relative to it. We honor that contract rather than inventing one.

CASE-INSENSITIVE PATH RESOLUTION IS DELIBERATE. The library's own entry
point currently names CATALOG/COLLECTIONS.json while the file on disk is
collections.json. That works on Windows and fails on macOS and Linux. Since
this tool is model- and platform-agnostic, we resolve case-insensitively and
report the mismatch as a fixable warning rather than dying on it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCATION_FILE = ROOT / ".library-location.json"
ENTRY_POINT = "START_HERE_FOR_ROBOTS.json"

# What each distribution bundle is expected to contain. Paths are relative to
# the library root and resolved case-insensitively.
ESSENTIALS = [
    "START_HERE_FOR_ROBOTS.json",
    "PORTABLE_LIBRARY_INDEX.json",
    "ROBOT_READABLE_DIRECTORY/MANIFESTS/documents.jsonl",
    "ROBOT_READABLE_DIRECTORY/MANIFESTS/DOHA_CURRENT_PATHS.jsonl",
    "ROBOT_READABLE_DIRECTORY/MANIFESTS/DOHA_SEAD4_SEARCH_ROUTER.json",
    "ROBOT_READABLE_DIRECTORY/CATALOG/collections.json",
    "ROBOT_READABLE_DIRECTORY/CATALOG/aliases.json",
]
SEARCH_TIER = [
    "LOCAL_INDEXES/DCSA_DOHA_DECISIONS_FTS.sqlite",
    "LOCAL_INDEXES/DCSA_GENERAL_FTS.sqlite",
]
SOURCE_TIER = ["HUMAN_READABLE_DIRECTORY"]

# Not distributed to users: maintainer build history, audit trails, migration
# journals. Present in the maintainer's master copy, absent from every bundle.
MAINTAINER_ONLY = ["OPERATIONS", "ARCHIVE"]


def clean_user_path(raw: str) -> Path:
    return Path(str(raw).strip().strip('"').strip("'")).expanduser()


def _candidates() -> list[Path]:
    home = Path.home()
    return [
        home / "Documents" / "DCSA Library",
        home / "DCSA Library",
        home / "Downloads" / "DCSA Library",
        home / "OneDrive" / "Documents" / "DCSA Library",
    ]


def resolve(cli_path: str | None = None) -> tuple[Path | None, str]:
    """Return (library_root, provenance). library_root is None if not found."""
    if cli_path:
        return clean_user_path(cli_path), "--library flag"
    env = os.environ.get("AIA_LIBRARY")
    if env:
        return clean_user_path(env), "AIA_LIBRARY environment variable"
    if LOCATION_FILE.exists():
        try:
            data = json.loads(LOCATION_FILE.read_text(encoding="utf-8"))
            p = data.get("library_path")
            if p:
                return Path(p), f"remembered location ({LOCATION_FILE.name})"
        except Exception:  # noqa: BLE001 — a corrupt memory file falls through
            pass
    for c in _candidates():
        if (c / ENTRY_POINT).is_file():
            return c, "found in a conventional location"
    return None, "not found"


def find_ci(root: Path, relative: str) -> tuple[Path | None, bool]:
    """Resolve a library-relative path, case-insensitively.

    Returns (resolved_path_or_None, exact_case_matched).

    Deliberately does NOT use Path.exists() as a fast path. On Windows and
    on default macOS filesystems that call is case-insensitive, so a claim
    of CATALOG/COLLECTIONS.json would "exist" even when the file on disk is
    catalog/collections.json — reporting an inexact match as exact and
    hiding the very defect this function exists to detect. Comparing
    against real directory entries keeps behaviour identical on every
    platform, which is the whole point: the maintainer builds on Windows,
    the bug only bites on Linux and macOS.
    """
    current = root
    exact = True
    for part in relative.replace("\\", "/").split("/"):
        if not part:
            continue
        if not current.is_dir():
            return None, False
        entries = list(current.iterdir())
        hit = next((c for c in entries if c.name == part), None)
        if hit is None:
            hit = next((c for c in entries if c.name.lower() == part.lower()), None)
            if hit is None:
                return None, False
            exact = False
        current = hit
    return current, exact


def is_library_root(path: Path) -> bool:
    return (path / ENTRY_POINT).is_file() or find_ci(path, ENTRY_POINT)[0] is not None


def detect_tier(root: Path) -> str:
    """Which distribution bundle is present: none | partial | essentials |
    search | complete."""
    have_essentials = all(find_ci(root, p)[0] for p in ESSENTIALS)
    if not have_essentials:
        return "partial" if find_ci(root, ENTRY_POINT)[0] else "none"
    if not all(find_ci(root, p)[0] for p in SEARCH_TIER):
        return "essentials"
    human, _ = find_ci(root, SOURCE_TIER[0])
    if human and human.is_dir() and any(human.rglob("*.pdf")):
        return "complete"
    return "search"


TIER_MEANING = {
    "complete": "Full library — guideline text, decisions, full-text search, "
                "and the original PDFs.",
    "search": "Text and search — everything the tool needs, plus full-text "
              "search across decisions. No source PDFs for human reading.",
    "essentials": "Essentials — the tool works: real guideline text, real "
                  "reporting authorities, case metadata and locations. No "
                  "full-text search across decision text.",
    "partial": "INCOMPLETE — the entry point is here but required manifests "
               "are missing. Some grounding is unavailable.",
    "none": "Not a library — no START_HERE_FOR_ROBOTS.json found.",
}


def missing_from(root: Path, items: list[str]) -> list[str]:
    return [p for p in items if not find_ci(root, p)[0]]


def require(cli_path: str | None = None, out=sys.stderr) -> Path | None:
    """Resolve the library, printing provenance. Returns None if absent.

    Absence is NOT fatal — the tool is designed to run without the library and
    say so. Callers decide whether they can proceed.
    """
    path, provenance = resolve(cli_path)
    if path is None:
        print(
            "library: NOT FOUND. The tool will run, but it cannot quote "
            "guideline text or cite any decision.\n"
            "  Run:  python scripts/check_library.py \"<path to DCSA Library>\" --remember",
            file=out,
        )
        return None
    print(f"library: {path}  (from {provenance})", file=out)
    if not is_library_root(path):
        print(
            f"  WARNING: no {ENTRY_POINT} in that folder — it does not look "
            "like the DCSA Library. Treating the library as absent.",
            file=out,
        )
        return None
    return path


def load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out
