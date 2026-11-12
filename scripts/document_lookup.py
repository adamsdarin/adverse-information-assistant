#!/usr/bin/env python3
"""Document retrieval aid. Tells the documents advisor HOW a record is
obtained — which office, which form or portal, what identification, how long
it takes — and what to do when the original is lost.

This is directory information, not legal or immigration advice, and not a
promise about any agency's process. Forms are renumbered and fees change, so
every entry ships unverified and the output says so. The advisor OFFERS an
entry to the user; it never asserts one, and it never fetches any URL here —
`--check-links` lists them for a human to open by hand and makes no network
call, by architecture.

Same contract as scripts/court_lookup.py: propose, let the user confirm,
record what the user says they will do.

Usage:
  python scripts/document_lookup.py --doc court-record
  python scripts/document_lookup.py --doc driving-record --state IA   # names Iowa's motor-vehicle agency
  python scripts/document_lookup.py --for-guideline F      # every readiness document for F, with its retrieval entry
  python scripts/document_lookup.py --list
  python scripts/document_lookup.py --check-links
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

import corpus_paths

FALLBACK = (
    "Ask the office that holds this record how to request a copy, what "
    "identification it needs, and how long it takes. Your security office can "
    "also tell you what form of the record it will accept. Do not delay the "
    "report while you wait."
)

USAGE_RULE = (
    "Offer, never assert. Read the request path as the way people usually "
    "obtain this record and the lead time as approximate; say the entry is "
    "unverified when it is. Record what the user says they will do, never this "
    "suggestion. Never fetch the URL — hand it to the user to open."
)


def load(corpus: Path) -> dict:
    path = corpus / "documents" / "retrieval.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_readiness(corpus: Path) -> dict:
    path = corpus / "checklists" / "_ADJUDICATIVE_READINESS.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_state_sources(corpus: Path) -> dict:
    """The per-state custodian directory kept beside state-courts.yaml:
    dmv, tax, criminal_history and child_welfare agencies for 51
    jurisdictions, plus national front doors. Absent is fine — the entry's
    generic request path still stands."""
    path = corpus / "courts" / "state-records-sources.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def index(data: dict) -> dict[str, dict]:
    return {e["id"]: e for e in data.get("entries", []) if isinstance(e, dict) and e.get("id")}


def describe(entry: dict, state_sources: dict | None = None, state: str | None = None) -> dict:
    """The entry as the advisor reads it to the user."""
    obtain = entry.get("obtainable_by")
    out = {
        "id": entry.get("id"),
        "label": entry.get("label"),
        "verified": bool(entry.get("verified")),
        "confidence": "verified" if entry.get("verified") else "unverified_directory_information",
        "obtainable_by": obtain,
        "custodian": entry.get("custodian"),
        "how_to_request": " ".join(str(entry.get("request_path", "")).split()),
        "form_or_portal": entry.get("form_or_portal"),
        "identity_needed": entry.get("identity_needed"),
        "typical_lead_time": entry.get("typical_lead_time"),
        "cost": entry.get("cost"),
        "if_the_original_is_lost": " ".join(str(entry.get("lost_original", "")).split()),
        "replacement_lead_time": entry.get("replacement_lead_time"),
        "all_pages": bool(entry.get("all_pages")),
        "on_letterhead": bool(entry.get("on_letterhead")),
        "source_url": entry.get("source_url"),
        "notes": " ".join(str(entry.get("notes", "")).split()) or None,
        "ask_first": "Do you have this in hand, or will you need to request it?",
        "usage_rule": USAGE_RULE,
    }
    # State-specific custodian and national front doors, when the directory
    # beside state-courts.yaml is present. Same contract: a pointer the user
    # opens, offered as "the agency that usually holds this".
    sources = state_sources or {}
    key = entry.get("state_directory_key")
    if key:
        out["state_directory_key"] = key
        st = (sources.get("states") or {}).get(state) if state else None
        if st and isinstance(st.get(key), dict):
            out["state_custodian"] = {
                "state": state,
                "state_name": st.get("name"),
                "agency": st[key].get("name"),
                "url": st[key].get("url"),
                "direct_url": st[key].get("direct_url"),
                "note": st[key].get("note"),
                "verified": bool(st.get("verified")),
            }
        elif state:
            out["state_custodian"] = {"state": state, "error": "no directory entry for this state",
                                      "fallback": FALLBACK}
        else:
            out["state_custodian"] = {"hint": "pass --state XX to name the agency for the user's state"}
    refs = entry.get("national_ref") or []
    if refs:
        national = {n.get("id"): n for n in sources.get("national") or [] if isinstance(n, dict)}
        out["national_sources"] = [
            {"id": r, "label": national[r].get("label"), "url": national[r].get("url")}
            if r in national else {"id": r, "error": "no national entry"}
            for r in refs
        ]
    if obtain == "security_office":
        out["ask_first"] = None
        out["user_task"] = (
            "None. This record is held by your security office; the package "
            "names it so the office knows to include it."
        )
    elif obtain == "third_party_only":
        out["user_task"] = (
            "Ask the person whose document it is for a copy and attach what "
            "they give you. Nothing from it is typed into this session, and a "
            "refusal is simply noted."
        )
    else:
        out["user_task"] = "Request it as described; report it as pending until it arrives."
    return out


def for_guideline(readiness: dict, entries: dict[str, dict], g: str,
                  state_sources: dict | None = None, state: str | None = None) -> dict:
    entry = (readiness.get("guidelines") or {}).get(g)
    if not entry:
        return {"error": f"no readiness entry for guideline {g!r}"}
    docs = []
    for d in entry.get("documents") or []:
        refs = d.get("retrieval_ref") or []
        if isinstance(refs, str):
            refs = [refs]
        docs.append({
            "type": d.get("type"),
            "custodian": d.get("custodian"),
            "obtain_by": d.get("obtain_by"),
            "applies_when": d.get("applies_when"),
            "retrieval": [describe(entries[r], state_sources, state) if r in entries
                          else {"id": r, "error": "no retrieval entry", "fallback": FALLBACK}
                          for r in refs],
        })
    return {"guideline": g, "statement_must_address": entry.get("statement_must_address"),
            "documents": docs, "usage_rule": USAGE_RULE}


def check_links(data: dict, state_sources: dict | None = None) -> int:
    """Report URLs for manual checking. Deliberately does NOT fetch anything —
    this tool makes no network calls, by architecture."""
    rows = [(e["id"], e["source_url"]) for e in data.get("entries", [])
            if isinstance(e, dict) and e.get("source_url")]
    sources = state_sources or {}
    for n in sources.get("national") or []:
        if isinstance(n, dict) and n.get("url"):
            rows.append((f"national:{n.get('id')}", n["url"]))
    for code, st in sorted((sources.get("states") or {}).items()):
        for key in ("dmv", "tax", "criminal_history", "child_welfare"):
            if isinstance(st.get(key), dict) and st[key].get("url"):
                rows.append((f"{code}:{key}", st[key]["url"]))
    print(f"{len(rows)} URLs to check by hand (this script makes no network calls):\n")
    for eid, url in rows:
        print(f"  {eid:42} {url}")
    print("\nOpen each, confirm it loads and still describes the same process, then set")
    print("verified: true with verified_date for that entry or state.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Document retrieval aid")
    ap.add_argument("--doc", help="retrieval entry id, e.g. court-record")
    ap.add_argument("--for-guideline", help="guideline letter A-M: every readiness document with its retrieval entry")
    ap.add_argument("--list", action="store_true", help="list entry ids and labels")
    ap.add_argument("--state", help="two-letter state code: attach that state's agency for state-held records")
    ap.add_argument("--check-links", action="store_true")
    ap.add_argument("--corpus", help="corpus root")
    args = ap.parse_args()

    corpus = corpus_paths.require(args.corpus)
    data = load(corpus)
    if not data:
        print(json.dumps({"error": "documents/retrieval.yaml not found",
                          "fallback": FALLBACK}, indent=2))
        return 1
    entries = index(data)
    state_sources = load_state_sources(corpus)
    state = args.state.strip().upper() if args.state else None

    if args.check_links:
        return check_links(data, state_sources)
    if args.list:
        for eid, e in sorted(entries.items()):
            flag = "" if e.get("verified") else "  (unverified)"
            print(f"{eid:42} {e.get('obtainable_by', ''):18} {e.get('label', '')}{flag}")
        return 0
    if args.for_guideline:
        g = args.for_guideline.strip().upper()
        out = for_guideline(load_readiness(corpus), entries, g, state_sources, state)
        print(json.dumps(out, indent=2))
        return 1 if "error" in out else 0
    if not args.doc:
        ap.error("give --doc, --for-guideline, --list or --check-links")

    entry = entries.get(args.doc.strip().lower())
    if not entry:
        print(json.dumps({"error": f"no entry for {args.doc!r}",
                          "fallback": FALLBACK}, indent=2))
        return 1
    print(json.dumps(describe(entry, state_sources, state), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
