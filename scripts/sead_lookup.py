#!/usr/bin/env python3
"""Resolve which SEAD directive sections to read — and read no more than those.

THE POINT
---------
Loading a whole directive to answer a question about one guideline puts twelve
other guidelines in front of the model. That is the condition under which text
gets attributed to the wrong guideline: not malice, just proximity. The
directives are split into one file per section, so when a matter implicates
Guideline B, the text of Guideline L is not in the context window and cannot be
misquoted.

WHY THIS IS A SCRIPT AND NOT AN INSTRUCTION
-------------------------------------------
"Read only the sections you need" is a request. An agent under time pressure
reads the whole folder; an agent that cannot find a file reads the parent
directory; an agent that is confident skips the lookup entirely. None of that
is visible downstream.

So selection is a computation. The caller passes guideline letters or an access
tier and gets back an explicit list of paths. If a section is missing, this
script says so and returns nothing for it — it never falls back to the full
directive, because a silent fallback is exactly the failure the split exists to
prevent.

Usage:
  python scripts/sead_lookup.py --guidelines G,J
  python scripts/sead_lookup.py --reporting --access ts_q
  python scripts/sead_lookup.py --isl --isl-tables 1,4
  python scripts/sead_lookup.py --isl --verifies corpus/reporting/tables/top-secret-q.yaml
  python scripts/sead_lookup.py --guidelines B --json
  python scripts/sead_lookup.py --status

Exit 0 = every requested section resolved. Exit 1 = something is missing, and
what is missing is printed. Treat a non-zero exit as "quote nothing".
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import library_paths as lp  # noqa: E402

GUIDELINE_NAMES = {
    "A": "Allegiance to the United States", "B": "Foreign Influence",
    "C": "Foreign Preference", "D": "Sexual Behavior", "E": "Personal Conduct",
    "F": "Financial Considerations", "G": "Alcohol Consumption",
    "H": "Drug Involvement and Substance Misuse",
    "I": "Psychological Conditions", "J": "Criminal Conduct",
    "K": "Handling Protected Information", "L": "Outside Activities",
    "M": "Use of Information Technology",
}

ISL_TABLE_NAMES = {
    "1": "Adverse Information Reporting Requirements",
    "2": "Reporting Requirements for All Covered Individuals",
    "3": "Top Secret and \u201cQ\u201d Access",
    "4": "Foreign Travel Reporting",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--library", help="path to the DCSA Library")
    ap.add_argument("--guidelines", help="SEAD 4 letters, e.g. 'G,J'")
    ap.add_argument("--reporting", action="store_true",
                    help="SEAD 3 reporting requirements")
    ap.add_argument("--access", default="baseline",
                    choices=["baseline", "ts_q", "not_applicable"],
                    help="access tier for --reporting (default: baseline)")
    ap.add_argument("--isl", action="store_true",
                    help="ISL 2021-02 — DCSA's implementation of SEAD 3 for "
                         "cleared industry, and the source of record for the "
                         "corpus reporting tables")
    ap.add_argument("--isl-tables",
                    help="ISL table numbers, e.g. '1,4'. Omit to get all four.")
    ap.add_argument("--verifies",
                    help="corpus table path(s), comma separated — returns the "
                         "ISL section that is source of record for each")
    ap.add_argument("--no-data-elements", action="store_true",
                    help="omit Appendix A required data elements")
    ap.add_argument("--status", action="store_true",
                    help="report what directive text is available")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root, how = lp.resolve(args.library)
    if not root or not lp.is_library_root(root):
        msg = ("The DCSA Library was not found, so no directive text can be "
               "quoted. Locate it with `python scripts/check_library.py "
               "\"<path>\" --remember`.")
        print(json.dumps({"ok": False, "problems": [msg]}) if args.json else msg)
        return 1

    health = lp.readiness(root)
    if not health["ready"]:
        msg = "Library is not approved for retrieval: " + "; ".join(health["errors"])
        print(json.dumps({"ok": False, "problems": [msg]}) if args.json else msg)
        return 1

    if args.status:
        st = lp.sead_split_status(root)
        if args.json:
            print(json.dumps(st, indent=2))
        else:
            print(f"Library: {root}  ({how})")
            print(f"  SEAD-3 sections: {'present' if st['sead3'] else 'ABSENT'}")
            print(f"  SEAD-4 sections: {'present' if st['sead4'] else 'ABSENT'}"
                  + (f"  guidelines {''.join(st['guidelines'])}"
                     if st["guidelines"] else ""))
            print(f"  ISL 2021-02:     {'present' if st['isl'] else 'ABSENT'}"
                  + (f"  tables {','.join(st['isl_tables'])}"
                     if st["isl_tables"] else ""))
            for p in st["problems"]:
                print(f"  ! {p}")
            if not st["problems"]:
                print("  Directive text can be quoted section by section.")
        return 0 if not st["problems"] else 1

    if args.isl_tables or args.verifies:
        args.isl = True
    if not args.guidelines and not args.reporting and not args.isl:
        ap.error("give --guidelines, --reporting, --isl, or --status")

    paths: list[Path] = []
    problems: list[str] = []
    letters: list[str] = []
    isl_tables: list[str] = []
    if args.guidelines:
        letters = [g.strip().upper() for g in args.guidelines.split(",") if g.strip()]
        bad = [g for g in letters if g not in GUIDELINE_NAMES]
        if bad:
            problems.append(f"not SEAD 4 guideline letters: {', '.join(bad)}")
            letters = [g for g in letters if g in GUIDELINE_NAMES]
        p, pr = lp.guideline_text(root, letters)
        paths += p
        problems += pr
    if args.reporting:
        p, pr = lp.reporting_text(root, args.access,
                                 include_data_elements=not args.no_data_elements)
        paths += p
        problems += pr
    if args.isl:
        wanted_tables = [t.strip() for t in (args.isl_tables or "").split(",") if t.strip()]
        bad = [t for t in wanted_tables if t not in ISL_TABLE_NAMES]
        if bad:
            problems.append(f"not ISL 2021-02 table numbers: {', '.join(bad)}")
            wanted_tables = [t for t in wanted_tables if t in ISL_TABLE_NAMES]
        verifies = [v.strip() for v in (args.verifies or "").split(",") if v.strip()]
        p, pr = lp.isl_text(root, wanted_tables or None, verifies or None)
        paths += p
        problems += pr
        isl_tables = wanted_tables

    ok = not problems
    if args.json:
        print(json.dumps({
            "ok": ok,
            "read_only_these": [str(x) for x in paths],
            "guidelines": letters,
            "access": args.access if args.reporting else None,
            "isl_tables": isl_tables if args.isl else None,
            "problems": problems,
        }, indent=2))
    else:
        if letters:
            print("Guidelines: " + ", ".join(f"{g} ({GUIDELINE_NAMES[g]})"
                                             for g in letters))
        if args.isl and isl_tables:
            print("ISL tables: " + ", ".join(f"{t} ({ISL_TABLE_NAMES[t]})"
                                             for t in isl_tables))
        print("\nREAD ONLY THESE FILES:")
        for x in paths:
            print(f"  {x}")
        if problems:
            print("\nPROBLEMS — do not substitute the full directive:")
            for x in problems:
                print(f"  ! {x}")
        print("\nDo not read any other file in these folders. A section not "
              "listed above\nis not part of this matter and its text must not "
              "appear in the output.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
