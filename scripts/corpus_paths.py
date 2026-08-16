#!/usr/bin/env python3
"""Single authority for locating the corpus. Every script resolves through
here, so the trust anchor and the corpus-location design cannot disagree.

Resolution order (first hit wins):
  1. An explicit --corpus PATH passed by the caller
  2. The AIA_CORPUS environment variable
  3. .corpus-location.json, written by `check_corpus.py <path> --remember`
  4. The default local path from corpus-sources.yaml (normally ./corpus)

The corpus lives wherever the user chose to put it — possibly a vastly
different location or structure. A structural deviation is therefore not a
silent fallback: it is HEAVILY flagged, because a session grounded against a
folder that merely resembles the corpus is worse than a session that knows it
has nothing.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "corpus-sources.yaml"


def _spec() -> dict:
    if not SOURCES.exists():
        return {}
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}


def _remembered_file(spec: dict) -> Path:
    return ROOT / spec.get("remembered_path_file", ".corpus-location.json")


def clean_user_path(raw: str) -> Path:
    """Users paste paths with quotes and trailing spaces constantly."""
    return Path(raw.strip().strip('"').strip("'")).expanduser()


def resolve(cli_path: str | None = None) -> tuple[Path, str]:
    """Return (corpus_root, provenance) without judging the folder's contents.

    provenance is a human-readable note on WHERE the path came from, so every
    script can say which authority it trusted.
    """
    spec = _spec()
    if cli_path:
        return clean_user_path(cli_path), "--corpus flag"
    env = os.environ.get("AIA_CORPUS")
    if env:
        return clean_user_path(env), "AIA_CORPUS environment variable"
    remembered = _remembered_file(spec)
    if remembered.exists():
        try:
            data = json.loads(remembered.read_text(encoding="utf-8"))
            p = data.get("corpus_path")
            if p:
                return Path(p), f"remembered location ({remembered.name})"
        except Exception:  # noqa: BLE001 — a corrupt memory file falls through
            pass
    return ROOT / spec.get("default_local_path", "./corpus"), "default ./corpus"


def structure_report(path: Path) -> tuple[list[str], list[str]]:
    """(missing_dirs, missing_files) against expected_structure in the spec."""
    exp = _spec().get("expected_structure", {})
    missing_dirs = [d for d in exp.get("required_directories", []) if not (path / d).is_dir()]
    missing_files = [f for f in exp.get("required_files", []) if not (path / f).is_file()]
    return missing_dirs, missing_files


def looks_like_wrong_folder(path: Path, missing_dirs: list[str]) -> bool:
    """A wrong folder is missing nearly everything; a real-but-partial corpus
    still has its skeleton."""
    required = _spec().get("expected_structure", {}).get("required_directories", [])
    return len(missing_dirs) >= max(2, len(required) // 2)


def require(cli_path: str | None = None, out=sys.stderr) -> Path:
    """Resolve the corpus root and refuse to proceed against a wrong folder.

    Prints its provenance every time — a script that silently used a
    different corpus than the one the user thinks it used defeats the entire
    grounding design. A structural deviation that stops short of wrong-folder
    is loudly flagged but allowed (partial corpora are a supported state).
    """
    path, provenance = resolve(cli_path)
    print(f"corpus: {path}  (from {provenance})", file=out)

    if not path.is_dir():
        print(
            f"ERROR: corpus root {path} does not exist or is not a folder.\n"
            "Run:  python scripts/check_corpus.py <path-to-your-corpus> --remember",
            file=out,
        )
        sys.exit(2)

    missing_dirs, _missing_files = structure_report(path)
    if looks_like_wrong_folder(path, missing_dirs):
        print(
            "ERROR: that folder does not look like the corpus — it is missing "
            f"most of the required structure ({', '.join(missing_dirs)}).\n"
            "Refusing to proceed: running against a folder that merely resembles\n"
            "the corpus is indistinguishable from running against nothing.\n"
            "Run:  python scripts/check_corpus.py <path-to-your-corpus> --remember",
            file=out,
        )
        sys.exit(2)
    if missing_dirs:
        print(
            "WARNING - CORPUS STRUCTURE DEVIATES FROM THE EXPECTED LAYOUT.\n"
            f"  Missing: {', '.join(missing_dirs)}\n"
            "  Anything grounded in the missing parts is unavailable this session,\n"
            "  and reportability degrades to 'check with your security office'.",
            file=out,
        )
    return path
