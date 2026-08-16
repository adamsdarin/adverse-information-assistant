#!/usr/bin/env python3
"""Court recognition aid. Helps a user REMEMBER which court heard their case.

This does not determine jurisdiction and it is not legal advice. People
routinely do not know which court their case went through — they were arrested,
told where to show up, and paid a fine, and the court's name never registered.
This turns "I don't remember" into "yes, that was it" by offering the most
likely court so the user can confirm or correct.

THE USER'S ANSWER IS ALWAYS AUTHORITATIVE. The nudge is a prompt, never a
value to record. Same contract as the entity resolver: propose, confirm, and
never insert something unconfirmed.

Unverified states are labelled as guesses in the output. An agent may offer a
guess explicitly ("I think, but check me") and may never assert one.

Usage:
  python scripts/court_lookup.py --state IA --county "Black Hawk"
  python scripts/court_lookup.py --state NJ --offense dui
  python scripts/court_lookup.py --check-links     # find rotted URLs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

import corpus_paths

FALLBACK = (
    "Contact the clerk of court in the county or city where the arrest "
    "happened and ask for a certified copy of the disposition. If you are not "
    "sure which court that was, the clerk's office can tell you from your name "
    "and the approximate date."
)


def load(corpus: Path) -> dict:
    path = corpus / "courts" / "state-courts.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_nudge(st: dict, county: str | None, offense: str | None) -> str:
    """The sentence to READ ALOUD to a user who doesn't remember."""
    unit = st.get("unit_label", "County")
    felony = offense == "felony"
    court = st["trial_court_felony"] if felony else st["trial_court_misdemeanor"]
    where = f"{county} {unit}" if county else f"the {unit.lower()} where you were arrested"

    nudge = f"In {st['name']}, that's usually the {court} for {where}"
    if county and unit.lower() == "county" and court.lower().startswith(("district", "circuit", "superior")):
        nudge += f" — so, {county} {unit} {court.split()[0]} Court"
    nudge += "."

    # Don't re-offer a court we already named — in some states the likely court
    # IS one of the lower courts (New Jersey DWI, for instance).
    others = [c for c in st.get("lower_courts", [])
              if c.split(" (")[0].lower() not in court.lower()]
    if others:
        nudge += (f" It could also have been a {' or '.join(others)} "
                  f"if a city charged you rather than the {unit.lower()}.")
    if offense in ("dui", "owi", "dwi") and st.get("dui_note"):
        nudge += f" {st['dui_note']}"
    return nudge


def describe(st: dict, code: str, county: str | None, offense: str | None) -> dict:
    return {
        "state": code,
        "state_name": st["name"],
        "verified": bool(st.get("verified")),
        "confidence": "verified" if st.get("verified") else "unverified_guess",
        "nudge": build_nudge(st, county, offense),
        "ask_first": "What court did your case go through?",
        "records_custodian": st.get("records_custodian"),
        "statewide_portal": st.get("statewide_portal"),
        "judiciary_url": st.get("judiciary_url"),
        "lower_courts": st.get("lower_courts", []),
        "notes": st.get("notes"),
        "dui_note": st.get("dui_note"),
        "fallback_if_still_unknown": FALLBACK,
        "usage_rule": (
            "Ask the user first. Offer the nudge ONLY if they don't know. "
            "Record what they say, never this suggestion. If this entry is "
            "unverified, present it explicitly as a guess to check."
        ),
    }


def check_links(data: dict) -> int:
    """Report URLs for manual checking. Deliberately does NOT fetch anything —
    this tool makes no network calls, by architecture."""
    rows = []
    for code, st in sorted(data.get("states", {}).items()):
        for field in ("judiciary_url", "statewide_portal"):
            if st.get(field):
                rows.append((code, field, st[field]))
    print(f"{len(rows)} URLs to check by hand (this script makes no network calls):\n")
    for code, field, url in rows:
        print(f"  {code}  {field:18} {url}")
    print("\nOpen each, confirm it loads and is still the right page, then set")
    print("verified: true with source_url and verified_date for that state.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Court recognition aid")
    ap.add_argument("--state", help="two-letter state code, e.g. IA")
    ap.add_argument("--county", help="county/parish/city of arrest, if known")
    ap.add_argument("--offense", help="dui | owi | dwi | felony | misdemeanor")
    ap.add_argument("--check-links", action="store_true")
    ap.add_argument("--corpus", help="corpus root")
    args = ap.parse_args()

    corpus = corpus_paths.require(args.corpus)
    data = load(corpus)
    if not data:
        print(json.dumps({"error": "state-courts.yaml not found",
                          "fallback": FALLBACK}, indent=2))
        return 1

    if args.check_links:
        return check_links(data)
    if not args.state:
        ap.error("give --state or --check-links")

    st = data.get("states", {}).get(args.state.strip().upper())
    if not st:
        print(json.dumps({"error": f"no entry for {args.state!r}",
                          "fallback": FALLBACK}, indent=2))
        return 1
    print(json.dumps(describe(st, args.state.strip().upper(),
                              args.county, (args.offense or "").lower() or None),
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
