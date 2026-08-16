#!/usr/bin/env python3
"""Deterministic package assembly.

Assembly is a script, not an agent, so the substitution checklist, the blank
knowledgeable-parties template, the disclaimer, and the corpus version cannot
be dropped, reworded, or "improved" by a model. The narrative is the only
model-authored part; everything structural is template.

Usage:
  python scripts/assemble_package.py session.json -o output/package.md

Always use -o. Shell redirection (`> output/package.md`) writes UTF-16 on
Windows PowerShell, which the verifier then cannot read; -o writes UTF-8
explicitly on every platform. The corpus root is resolved through
scripts/corpus_paths.py (--corpus flag > AIA_CORPUS > remembered location >
./corpus), the same authority every other script uses.

session.json shape:
{
  "form": "sf86|pvq|incident_report",
  "population": "industry|federal",
  "events": [
    {
      "title": "Alcohol-related arrest",
      "guidelines": ["G", "J"],
      "narrative": "<model-authored first-person statement>",
      "reporting": {"reportable": "yes", "channel": "...", "timeline": "...", "basis": ["aci.criminal.arrest"]},
      "crosswalk": [{"form_section": "22", "title": "Police Record"}],
      "documents": [{"name": "Certified court disposition", "source": "...", "timing": "can_follow"}],
      "persons": [{"label": "Person 1", "role": "my supervisor"}],
      "declined_elements": ["current-relationship"]
    }
  ]
}
"""
import argparse
import json
import sys
from pathlib import Path

import corpus_paths

DISCLAIMER = """\
## Disclaimer

This document was prepared with the assistance of an open-source tool that is
**not affiliated with, endorsed by, sponsored by, or reviewed by** the Defense
Counterintelligence and Security Agency (DCSA), the Defense Office of Hearings
and Appeals (DOHA), the Office of the Director of National Intelligence, or any
agency of the United States Government.

The U.S. Government makes all adjudicative determination decisions regarding
security clearance eligibility. This tool ensures no outcome of any kind. Its
only purpose is to help the undersigned provide complete and truthful
information. Nothing in this document is legal advice.

The undersigned is responsible for the accuracy of every statement here.
"""


def substitution_block(all_persons: list[dict], tier: str = "high") -> str:
    lines = [
        "## ACTION REQUIRED BEFORE YOU SUBMIT THIS",
        "",
        "This document is deliberately incomplete. The substitutions below are "
        "yours to make, and no one else can make them:",
        "",
        "1. **Replace every instance of `John Doe` with your legal name.**",
    ]
    if all_persons and tier == "high":
        lines += [
            "2. **Complete the knowledgeable-parties template at the end using your "
            "own mapping.** The numbered placeholders are identified nowhere in "
            "this tool and nowhere in this file — the note you kept is the only "
            "record of who they are.",
        ]
    elif all_persons:
        lines += [
            "2. **Complete the knowledgeable-parties template at the end.** Contact "
            "details were not collected at your chosen privacy level; fill them in "
            "immediately before submission.",
        ]
    else:
        lines += ["2. Verify every date and fact below. You sign it; you own it."]
    lines += [
        "",
        "Then read the whole statement. An automated check cannot tell whether "
        "a sentence understates what actually happened — only you can.",
        "",
    ]
    return "\n".join(lines)


def entities_section(entities: list[dict]) -> str:
    """Organizations are exempt from the privacy tiers and appear in full.

    Listed explicitly so the verifier can tell an allowed business address
    from a disallowed personal one — the string alone cannot.
    """
    if not entities:
        return ""
    out = ["## Entities Referenced", ""]
    for e in entities:
        out.append(f"### {e.get('name') or e.get('label')}")
        out.append(f"- Type: {e.get('type','').replace('_',' ')}")
        if e.get("address"):
            status = "confirmed by me" if e.get("confirmed_by_user") else "UNCONFIRMED"
            out.append(f"- Address: {e['address']} *({status})*")
        elif e.get("needs_user_supply"):
            out.append("- Address: ________________________________  *(you supply)*")
        if e.get("phone"):
            out.append(f"- Phone: {e['phone']}")
        out.append("")
    return "\n".join(out)


def privacy_header(tier: str) -> str:
    blurb = {
        # Deliberately avoids writing numbered placeholders literally. The
        # verifier counts every "Person N" in the document and requires a
        # template entry for each; boilerplate examples would trip that check
        # in the legitimate case where nobody else knows about the matter.
        "high": "**Privacy: HIGH.** No person is named anywhere below. Other people "
                "appear as numbered placeholders rather than by name. You hold the only "
                "record of who they are — use your mapping to fill in the template "
                "before you submit.",
        "medium": "**Privacy: MEDIUM.** People are named below, but no phone numbers, "
                  "emails, or addresses were collected. Complete those on the template.",
        "low": "**Privacy: LOW.** Contact details for other people were collected and "
               "appear below. Review them before sharing this document.",
    }.get(tier, "")
    if not blurb:
        return ""
    return blurb + "\n\nNo Social Security number or date of birth appears in this " \
                   "document at any privacy level — those go directly on the form.\n"


def outstanding_required(items: list[dict]) -> str:
    """Required form/reporting fields still unanswered.

    These are NOT the same as declined optional questions. A required field
    the user couldn't answer yet stays visible and loud, because a report
    missing it is incomplete on its face rather than merely brief. Silence
    here would let an incomplete package read as finished.
    """
    if not items:
        return ""
    out = [
        "## STILL REQUIRED — this report is not complete without these",
        "",
        "The following are required by the form or the reporting requirement "
        "and were not answered during this session. Get them before you file, "
        "or tell your FSO explicitly that they are outstanding.",
        "",
    ]
    for it in items:
        src = it.get("source_ref", "")
        where = f" — {src}" if src else ""
        out.append(f"- **{it.get('element')}**{where}")
        if it.get("how_to_get"):
            out.append(f"  - {it['how_to_get']}")
    out.append("")
    out.append(
        "*Do not delay a mandatory report to finish this list. Report now, "
        "supply these as they come in.*"
    )
    out.append("")
    return "\n".join(out)


def data_you_must_supply(items: list[dict]) -> str:
    """Form fields requiring third-party identity that the tool never collects.

    The PVQ requires names, phones, emails, and addresses in several places —
    counselor or treatment provider (19), bankruptcy trustee (23), relatives
    (21), foreign contacts (25), co-owners (26), people who know you well (10).
    This tool does not collect any of that. Instead it tells the user exactly
    what the form will demand, so they can gather it themselves. Naming the
    requirement is the help; holding the data is not.
    """
    if not items:
        return ""
    out = [
        "## Information You Will Need — NOT COLLECTED HERE",
        "",
        "The form asks for details about other people that this tool "
        "deliberately never asked you for and does not store. Gather these "
        "before you sit down to complete the form:",
        "",
    ]
    for it in items:
        out.append(f"### {it.get('form')} Section {it.get('section')} — {it.get('title','')}")
        for f in it.get("needs", []):
            out.append(f"- {f}")
        out.append("")
    return "\n".join(out)


def persons_template(all_persons: list[dict]) -> str:
    if not all_persons:
        return ""
    out = [
        "## Knowledgeable Parties — COMPLETE BEFORE SUBMISSION",
        "",
        "The tool that produced this document did not collect, store, or "
        "transmit any information about these individuals. Fill this in by "
        "hand for your security manager, SSO, or DCSA.",
        "",
    ]
    for p in all_persons:
        out += [
            f"### {p['label']}",
            f"- How they know: {p.get('role', '')}",
            "- Full name: ________________________________",
            "- Phone number: _____________________________",
            "- Email address: ____________________________",
            "- Mailing address: __________________________",
            "",
        ]
    return "\n".join(out)


def render_event(ev: dict, n: int, total: int) -> str:
    head = f"## Matter {n} of {total}: {ev.get('title', 'Reported matter')}" if total > 1 else "## Statement"
    parts = [head, "", ev.get("narrative", "").strip(), ""]

    rep = ev.get("reporting") or {}
    if rep.get("voluntary"):
        # Worth stating explicitly. Prompt, good-faith disclosure made before
        # being confronted is a recognized mitigating consideration, and a
        # reviewer cannot credit what the document does not tell them.
        parts += [
            "> **Voluntarily disclosed.** The undersigned raised this matter "
            "without being asked about it and without a policy requirement "
            "identified as compelling it.",
            "",
        ]
    if rep.get("reportable") == "yes":
        layers = rep.get("layers_applied") or []
        parts += [
            "### Reporting channel and timeline",
            f"- Channel: {rep.get('channel', 'see your security office')}",
            f"- Timeline: {rep.get('timeline', 'see your security office')}",
            f"- Basis: {', '.join(rep.get('basis', [])) or 'see your security office'}",
        ]
        if layers:
            parts.append(f"- Authority: {', '.join(layers)}")
        parts.append("")
    elif rep:
        parts += [
            "### Reporting channel and timeline",
            "- This tool could not confirm the requirement from its corpus. "
            "**Confirm with your security office.** This means the tool could "
            "not verify the answer, not that the matter is unreportable.",
            "",
        ]

    cw = ev.get("crosswalk") or []
    if cw:
        parts += ["### Form crosswalk", ""]
        for c in cw:
            unverified = " *(section unverified — confirm with your FSO)*" if c.get("unverified") else ""
            parts.append(f"- Section {c.get('form_section')}: {c.get('title','')}{unverified}")
        parts.append("")

    docs = ev.get("documents") or []
    if docs:
        parts += [
            "### Supporting documents",
            "",
            "*Do not delay this report while gathering these.*",
            "",
        ]
        for d in docs:
            timing = "before submission" if d.get("timing") == "before" else "may follow"
            parts.append(f"- {d.get('name')} — {d.get('source','')} ({timing})")
        parts.append("")

    declined = ev.get("declined_elements") or []
    if declined:
        parts += [
            "### Not addressed",
            "",
            "The following were not answered and are therefore not addressed "
            "above. They are listed rather than filled in, so nothing here "
            "implies more than was said:",
            "",
        ] + [f"- {d}" for d in declined] + [""]

    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Assemble the deliverable package from session.json")
    ap.add_argument("session", help="path to session.json")
    ap.add_argument("-o", "--output",
                    help="write the package here as UTF-8 (always prefer this "
                         "over shell redirection, which writes UTF-16 on "
                         "Windows PowerShell)")
    ap.add_argument("--corpus", help="corpus root (overrides remembered location)")
    args = ap.parse_args()

    corpus = corpus_paths.require(args.corpus)
    version_file = corpus / "VERSION"
    if not version_file.is_file():
        print(
            f"ERROR: {version_file} missing. The package must record the corpus "
            "version it was built against; refusing to assemble an untraceable "
            "package. Run scripts/check_corpus.py on your corpus first.",
            file=sys.stderr,
        )
        return 1
    version = version_file.read_text(encoding="utf-8").split()[0]

    session = json.loads(Path(args.session).read_text(encoding="utf-8"))
    events = session.get("events", [])

    all_persons: list[dict] = []
    seen = set()
    for ev in events:
        for p in ev.get("persons", []):
            if p["label"] not in seen:
                seen.add(p["label"])
                all_persons.append(p)

    tier = session.get("privacy_tier", "high")
    doc = [
        "# Adverse Information Report — John Doe",
        "",
        privacy_header(tier),
        "",
        substitution_block(all_persons, tier),
        "---",
        "",
    ]
    for i, ev in enumerate(events, 1):
        doc.append(render_event(ev, i, len(events)))
        doc.append("---")
        doc.append("")

    ents = session.get("entities", [])
    if ents:
        doc += [entities_section(ents), "---", ""]

    outstanding = session.get("outstanding_required", [])
    if outstanding:
        doc += [outstanding_required(outstanding), "---", ""]

    needed = session.get("data_you_must_supply", [])
    if needed:
        doc += [data_you_must_supply(needed), "---", ""]

    if all_persons:
        doc += [persons_template(all_persons), "---", ""]

    doc += [
        DISCLAIMER,
        "",
        f"*Corpus version: {version}*",
        "",
    ]
    text = "\n".join(doc)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"Wrote {out} (UTF-8)", file=sys.stderr)
    else:
        print(
            "WARNING: no -o given. If you redirect stdout on Windows PowerShell "
            "the file will be UTF-16 and the verifier will not read it. "
            "Use:  assemble_package.py session.json -o output/package.md",
            file=sys.stderr,
        )
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
