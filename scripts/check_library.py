#!/usr/bin/env python3
"""Validate the DCSA Library and say plainly what it can and cannot do.

The library is downloaded separately by the user and placed wherever they
like. This script decides whether the folder they pointed at is the real
thing, which distribution bundle they have, what is missing, and — most
usefully — what each gap costs a session.

THIS SCRIPT NEVER DOWNLOADS ANYTHING. If files are missing it names them,
says which bundle contains them, and points at the distribution link. That
is the whole repair story: instructions, never a network call. Government
sites block automation, and auto-fetched content would wear a verified
file's name without a human ever having checked it.

Usage:
  python scripts/check_library.py                          # search known spots
  python scripts/check_library.py "D:\\DCSA Library"
  python scripts/check_library.py "<path>" --remember
  python scripts/check_library.py --json                   # machine-readable

Exit: 0 usable (possibly partial) · 1 not a library / not found
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import library_paths as lp

DISTRIBUTION_NOTE = """\
The DCSA Library is not part of this repository. Download it from the link
in library-sources.yaml, unzip it anywhere you like, and point this script
at the folder that contains START_HERE_FOR_ROBOTS.json."""


def report(root: Path, as_json: bool) -> dict:
    tier = lp.detect_tier(root)
    missing_ess = lp.missing_from(root, lp.ESSENTIALS)
    missing_search = lp.missing_from(root, lp.SEARCH_TIER)

    # Check the paths the LIBRARY ITSELF declares, not just the ones this tool
    # wants. The entry point is a promise to every piece of software that reads
    # it; a promise naming CATALOG/COLLECTIONS.json when the file is
    # collections.json is kept on Windows and broken everywhere else.
    case_issues: list[str] = []
    broken_claims: list[str] = []
    for entry_rel in (lp.ENTRY_POINT,
                      "ROBOT_READABLE_DIRECTORY/RETRIEVAL/retrieval_config.json"):
        entry, _ = lp.find_ci(root, entry_rel)
        if not entry or not entry.is_file():
            continue
        try:
            declared = json.loads(entry.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            broken_claims.append(f"{entry_rel} is not valid JSON")
            continue
        claims: list[str] = []
        for v in declared.values():
            if isinstance(v, str) and "/" in v and not v.startswith("http"):
                claims.append(v)
            elif isinstance(v, list):
                claims += [x for x in v if isinstance(x, str) and "/" in x]
        for claim in claims:
            resolved, exact = lp.find_ci(root, claim)
            if resolved is None:
                broken_claims.append(f"{entry.name} points at {claim} — not present")
            elif not exact:
                case_issues.append(
                    f"{entry.name} says {claim} — on disk it is {resolved.name}")

    counts: dict[str, int] = {}
    groups: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    paths_file, _ = lp.find_ci(root, "ROBOT_READABLE_DIRECTORY/MANIFESTS/DOHA_CURRENT_PATHS.jsonl")
    if paths_file and paths_file.is_file():
        recs = lp.load_jsonl(paths_file)
        counts["doha_decisions"] = len(recs)
        for r in recs:
            groups[r.get("current_group", "?")] = groups.get(r.get("current_group", "?"), 0) + 1
            stem = str(r.get("case_stem", ""))
            parts = stem.split("_")
            oc = parts[1] if len(parts) > 1 else "?"
            outcomes[oc] = outcomes.get(oc, 0) + 1
    docs_file, _ = lp.find_ci(root, "ROBOT_READABLE_DIRECTORY/MANIFESTS/documents.jsonl")
    if docs_file and docs_file.is_file():
        counts["documents"] = sum(1 for _ in docs_file.open(encoding="utf-8"))

    # A manifest that references files this bundle does not include is NORMAL
    # for a tiered download — not corruption. Report it as a tier fact.
    shipped_maintainer = [d for d in lp.MAINTAINER_ONLY if lp.find_ci(root, d)[0]]

    data = {
        "library_path": str(root),
        "tier": tier,
        "tier_meaning": lp.TIER_MEANING[tier],
        "missing_essentials": missing_ess,
        "missing_search": missing_search,
        "case_mismatches": case_issues,
        "broken_entry_point_claims": broken_claims,
        "counts": counts,
        "doha_groups": groups,
        "doha_outcomes": outcomes,
        "maintainer_only_folders_present": shipped_maintainer,
    }
    if as_json:
        return data

    print(f"Library:  {root}")
    print(f"Bundle:   {tier.upper()}")
    print(f"          {lp.TIER_MEANING[tier]}\n")

    if counts:
        print("Contents:")
        if "documents" in counts:
            print(f"  Documents indexed:  {counts['documents']}")
        if "doha_decisions" in counts:
            print(f"  DOHA decisions:     {counts['doha_decisions']}")
            if groups:
                print(f"    by era:           {groups}")
            if outcomes:
                shown = {k: v for k, v in sorted(outcomes.items(), key=lambda x: -x[1])[:4]}
                print(f"    by outcome:       {shown}")
        print()

    if missing_ess:
        print("MISSING — required for the tool to ground anything:")
        for m in missing_ess:
            print(f"  - {m}")
        print()
    if missing_search and not missing_ess:
        print("Not present (optional 'Search' bundle):")
        for m in missing_search:
            print(f"  - {m}")
        print()

    if case_issues:
        print("PATH CASE MISMATCH — works on Windows, FAILS on macOS and Linux:")
        for c in case_issues:
            print(f"  - {c}")
        print("  This tool resolves these anyway. Fix the library's entry point")
        print("  so other software doesn't break on it.\n")

    if broken_claims:
        print("ENTRY POINT POINTS AT FILES THAT AREN'T THERE:")
        for c in broken_claims:
            print(f"  - {c}")
        print("  Either the file is missing from this bundle, or the entry")
        print("  point names it wrongly. Everything else still works.\n")

    if shipped_maintainer:
        print("Maintainer-only folders present:", ", ".join(shipped_maintainer))
        print("  Fine on your own machine. These should NOT be in a bundle you")
        print("  distribute — they are build history, not reference material.\n")

    print("What this means for a session:")
    if tier in ("none", "partial"):
        print("  · The tool runs, but cannot quote guideline text.")
        print("  · No decision can be cited — an empty result is a valid result.")
        print("  · Reportability degrades to 'check with your security office'.")
    else:
        print("  · Guideline text and reporting authorities can be quoted.")
        print("  · Decisions can be cited, and every citation is checked against")
        print("    this library before any package is delivered.")
        if tier == "essentials":
            print("  · No full-text search across decision text — precedent questions")
            print("    come from case metadata only. Add the 'Search' bundle for more.")
        if tier in ("essentials", "search"):
            print("  · Source PDFs are not present. Nothing breaks; you just cannot")
            print("    open the original document to read it yourself.")
    print()
    print("This tool never downloads library content. If something is missing,")
    print("get it from the distribution link in library-sources.yaml.")
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate the DCSA Library")
    ap.add_argument("path", nargs="?", help="path to the DCSA Library folder")
    ap.add_argument("--remember", action="store_true",
                    help="record this location for every other script")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    if args.path:
        root = lp.clean_user_path(args.path)
        provenance = "given on the command line"
    else:
        root, provenance = lp.resolve()

    if root is None:
        print("DCSA LIBRARY NOT FOUND.\n")
        print(DISTRIBUTION_NOTE)
        print("\nThe tool still runs without it. It just cannot cite anything,")
        print("and it will say so rather than guessing.")
        return 1

    if not root.exists():
        print(f"NOT FOUND — nothing at {root}\n")
        print(DISTRIBUTION_NOTE)
        return 1
    if not root.is_dir():
        print(f"NOT A FOLDER — {root} is a file. Point at the folder that contains it.")
        return 1

    # The library declares its own root. Accept a parent folder gracefully:
    # users routinely point at the folder they unzipped INTO.
    if not lp.is_library_root(root):
        for child in sorted(p for p in root.iterdir() if p.is_dir()):
            if lp.is_library_root(child):
                print(f"Note: the library is one level down. Using {child}\n")
                root = child
                break
    if not lp.is_library_root(root):
        print("THIS DOES NOT LOOK LIKE THE DCSA LIBRARY.\n")
        print(f"Expected to find {lp.ENTRY_POINT} inside it, and did not.")
        print("You've probably pointed at a parent folder or the wrong download.")
        print("Look for the folder that directly contains START_HERE_FOR_ROBOTS.json")
        print("and HUMAN_READABLE_DIRECTORY.\n")
        print(DISTRIBUTION_NOTE)
        return 1

    if not args.json:
        print(f"Checking: {root}  ({provenance})\n")
    data = report(root, args.json)
    if args.json:
        print(json.dumps(data, indent=2))

    if args.remember:
        lp.LOCATION_FILE.write_text(
            json.dumps({
                "library_path": str(root.resolve()),
                "tier": data["tier"],
                "doha_decisions": data["counts"].get("doha_decisions", 0),
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        if not args.json:
            print(f"Remembered in {lp.LOCATION_FILE.name} (gitignored). Every "
                  "script will resolve the library from this file unless "
                  "overridden with --library or AIA_LIBRARY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
