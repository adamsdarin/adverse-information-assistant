#!/usr/bin/env python3
"""Find DOHA decisions in the library. Deterministic; no model involved.

Replaces the old hand-curated corpus/doha/cases/*.md + index.json. The
library already holds every published decision with its era, outcome, and
adjudicated guidelines encoded in `case_stem`:

    01-07620.h1_approved_b_c
    │        │  │        └── guidelines B and C
    │        │  └── outcome: approved | denied | remanded
    │        └── level: h1/h2/h3 hearing, a1/a2 appeal
    └── case number

so retrieval needs the 5 MB manifest, not the 364 MB full-text index. That
is what makes the small "Essentials" bundle genuinely useful.

Two rules from the library's own search router, enforced here rather than
left to a prompt:

  · POST_SEAD_4 is the default scope. Pre-SEAD-4 decisions are historical
    context and rank below it — they were decided under superseded criteria.
  · Both outcomes are returned deliberately. A denial-only sample produces a
    fear-shaped interview; a grant-only sample produces a credulous one.

NOTHING HERE PRODUCES A RATE, TENDENCY, OR PREDICTION. Published decisions
are contested SOR cases — a selection-biased sample that says nothing about
how ordinary reports resolve. Counts exist to balance retrieval, never to
tell a user what is likely to happen to them.

THREE DIFFERENT NUMBERS ARE ALL CORRECT, AND THEY ARE NOT THE SAME COUNT.
`check_library.py` reports every row of DOHA_CURRENT_PATHS.jsonl (10,658 as
of the 2026 library). `parsed_decision_count` below counts only the rows
whose `case_stem` parses AND whose outcome is approved/denied/remanded — a
handful of rows carry an unreadable OCR stem or an outcome like
"unreadable" and are dropped rather than guessed at (10,627). A case number
can have more than one published decision under it — a hearing followed by
an appeal, most commonly — so `unique_case_count` (10,327) collapses those
to distinct case numbers, which is what `--verify-case` checks membership
against. total >= parsed >= unique is the invariant; it is not a bug if the
three differ, only if the invariant breaks.

Usage:
  python scripts/doha_retrieval.py --guidelines G,J
  python scripts/doha_retrieval.py --guidelines F --limit 8 --include-pre-sead4
  python scripts/doha_retrieval.py --verify-case 24-01234
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import library_paths as lp

STEM_RE = re.compile(
    r"^(?P<case>\d{2}-\d{4,5})\.(?P<level>[ah]\d)_(?P<outcome>[a-z]+)"
    r"(?:_(?P<guidelines>[a-z](?:_[a-z])*))?$"
)
LEVELS = {"h": "hearing", "a": "appeal"}


def parse_stem(stem: str) -> dict | None:
    m = STEM_RE.match(str(stem).strip())
    if not m:
        return None
    g = m.group("guidelines")
    return {
        "case_no": m.group("case"),
        "level": LEVELS.get(m.group("level")[0], "unknown"),
        "outcome": m.group("outcome"),
        "guidelines": [x.upper() for x in g.split("_")] if g else [],
    }


def load_cases(root: Path) -> list[dict]:
    """Every decision the library knows about, parsed. Unparseable stems are
    dropped rather than guessed at — a wrong guideline tag sends an entire
    interview down the wrong track."""
    path, _ = lp.find_ci(root, "ROBOT_READABLE_DIRECTORY/MANIFESTS/DOHA_CURRENT_PATHS.jsonl")
    if not path or not path.is_file():
        return []
    cases = []
    for rec in lp.load_jsonl(path):
        parsed = parse_stem(rec.get("case_stem", ""))
        if not parsed:
            continue
        if parsed["outcome"] not in ("approved", "denied", "remanded"):
            continue  # 'unreadable' and friends carry no usable signal
        parsed.update({
            "document_id": rec.get("document_id"),
            "group": rec.get("current_group"),
            "era": rec.get("sead4_era"),
            "answer_eligible": rec.get("answer_eligible"),
            "text_path": rec.get("robot_text_path"),
            "source_path": rec.get("human_source_path"),
        })
        cases.append(parsed)
    return cases


def select(cases: list[dict], guidelines: list[str], limit: int = 6,
           include_pre_sead4: bool = False) -> list[dict]:
    """Rank by guideline overlap, era, then balance the outcomes."""
    want = {g.upper() for g in guidelines}
    scored = []
    for c in cases:
        if c.get('answer_eligible') is False and not (include_pre_sead4 and c['group'] == 'PRE_SEAD_4'):
            continue
        overlap = want & set(c["guidelines"])
        if not overlap:
            continue
        if c["group"] != "POST_SEAD_4" and not include_pre_sead4:
            continue
        score = (
            len(overlap) * 10
            + (5 if c["group"] == "POST_SEAD_4" else 0)
            - abs(len(c["guidelines"]) - len(want))  # prefer a tight match
        )
        scored.append((score, c))
    scored.sort(key=lambda x: (-x[0], x[1]["case_no"]))

    # Alternate outcomes so a caller taking the top N never gets one-sided
    # results. Denials show what absence looks like; grants show what a
    # complete record looks like. Both generate questions; only together do
    # they generate balanced ones.
    denied = [c for _, c in scored if c["outcome"] == "denied"]
    approved = [c for _, c in scored if c["outcome"] == "approved"]
    other = [c for _, c in scored if c["outcome"] not in ("denied", "approved")]
    out: list[dict] = []
    while len(out) < limit and (denied or approved):
        if denied:
            out.append(denied.pop(0))
        if len(out) < limit and approved:
            out.append(approved.pop(0))
    if len(out) < limit:
        out.extend(other[: limit - len(out)])
    return out[:limit]


def known_case_numbers(root: Path) -> set[str]:
    """Every case number in the library — the citation allowlist."""
    return {c["case_no"] for c in load_cases(root)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Retrieve DOHA decisions from the library")
    ap.add_argument("--guidelines", help="comma-separated letters, e.g. G,J")
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--include-pre-sead4", action="store_true",
                    help="include decisions predating SEAD 4 (historical context only)")
    ap.add_argument("--verify-case", help="check whether a case number exists")
    ap.add_argument("--library", help="library root (overrides remembered location)")
    args = ap.parse_args()

    root = lp.require(args.library)
    if root is None:
        print(json.dumps({"error": "library_not_found", "cases": []}, indent=2))
        return 1

    if args.verify_case:
        known = known_case_numbers(root)
        found = args.verify_case.strip() in known
        print(json.dumps({"case_no": args.verify_case, "in_library": found,
                          "unique_case_count": len(known)}, indent=2))
        return 0 if found else 1

    if not args.guidelines:
        ap.error("give --guidelines or --verify-case")

    cases = load_cases(root)
    picked = select(cases, [g.strip() for g in args.guidelines.split(",") if g.strip()],
                    args.limit, args.include_pre_sead4)
    print(json.dumps({
        "guidelines": args.guidelines,
        "parsed_decision_count": len(cases),
        "unique_case_count": len({c["case_no"] for c in cases}),
        "returned": len(picked),
        "scope": "POST_SEAD_4" + (" + PRE_SEAD_4 (historical)" if args.include_pre_sead4 else ""),
        "reminder": "These are contested SOR cases — a selection-biased sample. "
                    "Use them to generate questions. Never to state a rate, a "
                    "tendency, or a likely outcome.",
        "cases": picked,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
