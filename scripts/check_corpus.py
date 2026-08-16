#!/usr/bin/env python3
"""Verify a directory is a usable corpus, and report exactly what's in it.

The corpus lives outside the repo (see corpus-sources.yaml). A user points the
tool at a folder; this decides whether that folder is the real thing, a wrong
folder, or a valid-but-partial corpus — and says so plainly.

The distinction that matters: a PARTIAL corpus is normal and workable. A WRONG
FOLDER is not, and must never be treated as an empty corpus, because "running
with reduced capability" and "running against nothing" look identical to a user
unless someone says otherwise.

Usage:
  python scripts/check_corpus.py                 # check ./corpus
  python scripts/check_corpus.py "D:\\path\\to\\corpus"
  python scripts/check_corpus.py <path> --remember

Exit codes: 0 usable (possibly partial) · 1 not a corpus · 2 unreadable
"""
import json
import sys
from pathlib import Path

import yaml

import corpus_paths

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "corpus-sources.yaml"
GUIDELINES = list("ABCDEFGHIJKLM")


def load_spec() -> dict:
    if not SOURCES.exists():
        print(f"ERROR: {SOURCES.name} missing — cannot tell what a corpus should look like")
        sys.exit(2)
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}


def frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        _, fm, _ = text.split("---", 2)
        return yaml.safe_load(fm) or {}
    except Exception:
        return {}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    remember = "--remember" in sys.argv
    spec = load_spec()

    if args:
        # Users paste paths with surrounding quotes constantly, especially on
        # Windows where the path has spaces. Strip them rather than fail.
        path = corpus_paths.clean_user_path(args[0])
        provenance = "given on the command line"
    else:
        # No path given: honor a previously remembered location before the
        # default, exactly as the intake instructions promise.
        path, provenance = corpus_paths.resolve()

    print(f"Checking: {path}  ({provenance})\n")

    if not path.exists():
        print("NOT FOUND — nothing at that path.")
        print("\nCheck for a typo, or see corpus-sources.yaml for where to get the corpus.")
        return 1
    if not path.is_dir():
        print("NOT A FOLDER — that's a file. Point at the folder that contains it.")
        return 1

    exp = spec.get("expected_structure", {})
    missing_dirs = [d for d in exp.get("required_directories", []) if not (path / d).is_dir()]
    missing_files = [f for f in exp.get("required_files", []) if not (path / f).is_file()]

    # A wrong folder is missing nearly everything. A real corpus that is merely
    # unpopulated still has its skeleton.
    if len(missing_dirs) >= max(2, len(exp.get("required_directories", [])) // 2):
        print("THIS DOES NOT LOOK LIKE THE CORPUS.")
        print("\nExpected to find these folders inside it, and did not:")
        for d in missing_dirs:
            print(f"  - {d}")
        print("\nYou've probably pointed at a parent folder or the wrong download.")
        print("Look for the folder that directly contains 'sead4' and 'checklists'.")
        return 1

    # --- Coverage report -------------------------------------------------
    print("Structure: OK\n")
    if missing_dirs or missing_files:
        print("Incomplete, but usable. Missing:")
        for d in missing_dirs:
            print(f"  - {d}/")
        for f in missing_files:
            print(f"  - {f}")
        print()

    version = "unknown"
    vf = path / "VERSION"
    if vf.is_file():
        version = vf.read_text(encoding="utf-8").split()[0]

    # SEAD 4 guideline coverage
    verified_g, present_g = [], []
    for g in GUIDELINES:
        hits = list((path / "sead4").glob(f"guideline-{g}-*.md")) if (path / "sead4").is_dir() else []
        if hits:
            present_g.append(g)
            if frontmatter(hits[0]).get("verbatim"):
                verified_g.append(g)

    # DOHA cases
    cases_dir = path / "doha" / "cases"
    cases = [p for p in cases_dir.glob("*.md") if not p.name.startswith("_")] if cases_dir.is_dir() else []
    outcomes: dict[str, int] = {}
    for c in cases:
        o = frontmatter(c).get("outcome", "?")
        outcomes[o] = outcomes.get(o, 0) + 1

    # Reporting tables verified?
    tables_dir = path / "reporting" / "tables"
    tables, verified_tables = [], []
    if tables_dir.is_dir():
        for t in tables_dir.glob("*.yaml"):
            tables.append(t.name)
            try:
                if (yaml.safe_load(t.read_text(encoding="utf-8")) or {}).get("maintainer_verified"):
                    verified_tables.append(t.name)
            except Exception:
                pass

    print(f"Corpus version:     {version}")
    print(f"SEAD 4 guidelines:  {len(present_g)}/13 present, {len(verified_g)}/13 verified")
    print(f"DOHA cases:         {len(cases)}" + (f"  ({outcomes})" if outcomes else ""))
    print(f"Reporting tables:   {len(tables)} present, {len(verified_tables)} verified")

    # --- What this costs the user ---------------------------------------
    print("\nWhat this means for a session:")
    if len(verified_g) < 13:
        print("  · Guideline text cannot be quoted for unverified guidelines.")
    if not cases:
        print("  · No case precedent available — the interview runs off checklists alone.")
    elif len(outcomes) == 1:
        print(f"  · Only '{list(outcomes)[0]}' outcomes present. The corpus should hold both,")
        print("    or precedent-derived questions will be one-sided.")
    if not verified_tables:
        print("  · Reportability degrades to 'check with your security office' — the tool")
        print("    will not assert that something IS reportable from unverified tables.")
    if len(verified_g) == 13 and cases and verified_tables:
        print("  · Fully grounded. No degradation.")

    if remember:
        target = ROOT / spec.get("remembered_path_file", ".corpus-location.json")
        target.write_text(json.dumps({
            "corpus_path": str(path.resolve()),
            "corpus_version": version,
            "guidelines_verified": len(verified_g),
            "cases": len(cases),
            "structure_deviations": missing_dirs + missing_files,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"\nRemembered in {target.name} (gitignored). Every script will "
              "resolve the corpus from this file unless overridden with "
              "--corpus or AIA_CORPUS.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
