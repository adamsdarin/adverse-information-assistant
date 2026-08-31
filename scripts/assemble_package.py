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
      "crosswalk": [{
        "form": "sf86", "form_section": "22", "title": "Police Record",
        "unverified": false,
        "fields": [
          {"id": "offense_date", "label": "Date of offense", "block": null,
           "question": "Provide the date of the offense.", "answer": "March 2026"}
        ],
        "additional_comments_field": true
      }],
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

I am responsible for the accuracy of every statement in this report.
"""

PROCEEDING_BOUNDARY = """\
> **Separate-proceeding limitation.** This workflow cannot determine how a
> security report may interact with a separate criminal proceeding. It does
> not predict confidentiality, disclosure, discoverability, or evidentiary
> use, and it does not provide legal advice.
"""


def submission_route(session: dict) -> str:
    role = session.get("role")
    if role == "holder":
        text = (
            "I am providing each incident below to my FSO, security manager, "
            "SMO, or servicing security office for entry in DISS. The "
            "incident-type labels are listed with each independent incident; "
            "I understand that I do not personally enter information in DISS."
        )
    elif role == "in_process":
        text = (
            "I am notifying the SMO or security office sponsoring my pending "
            "investigation so it can ensure DCSA receives this information. "
            "I understand that the event may be addressed during my initial "
            "investigation depending on when it occurred, and that possibility "
            "is not a reason to delay or omit my report. The form crosswalks "
            "below are context, not an instruction to resubmit my form."
        )
    else:
        text = (
            "I will use each incident and its form crosswalk below when "
            "completing my initial SF-86 or PVQ. I have kept factually "
            "independent incidents separate while preserving one complete "
            "narrative for each."
        )
    return "## Final Reporting Analysis\n\n" + text + "\n"


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


def render_event(ev: dict, n: int, total: int, role: str) -> str:
    head = f"## Incident {n} of {total}: {ev.get('title', 'Reported incident')}"
    parts = [head, "", ev.get("narrative", "").strip(), ""]

    rep = ev.get("reporting") or {}
    if rep.get("voluntary"):
        # Worth stating explicitly. Prompt, good-faith disclosure made before
        # being confronted is a recognized mitigating consideration, and a
        # reviewer cannot credit what the document does not tell them.
        parts += [
            "> **Voluntarily disclosed.** I raised this matter without being "
            "asked about it and without an identified policy requirement "
            "compelling the disclosure.",
            "",
        ]
    pd = ev.get("prior_disclosure") or {}
    if pd.get("status") == "disclosed_unchanged":
        # Rendered as CONTEXT, not as a new report. The user says the
        # government already has this; the package should not read as though
        # they are disclosing it again, but it stays visible because the
        # narrative around it often depends on it.
        parts += [
            "> **Previously disclosed.** I disclosed this matter in a prior "
            "background investigation, and it has not changed since then. I "
            "include it here as context rather than as a new disclosure. No "
            "new reporting obligation was identified based on my account, "
            "which was not independently verified.",
            "",
        ]
    elif pd.get("status") == "disclosed_but_changed":
        parts += [
            "> **Previously disclosed, with a change since.** I disclosed the "
            f"underlying matter in a prior investigation. I am now reporting "
            f"this change: {pd.get('what_changed', 'see below')}",
            "",
        ]
    if pd.get("scope_concern"):
        parts += [
            "> **For my security office's review.** What I described in this "
            "session may be broader than what I disclosed previously. I am "
            "flagging that difference rather than resolving it myself.",
            "",
        ]

    if role == "holder":
        parts += ["### Applicable DISS incident type(s)", ""]
        for incident_type in ev.get("incident_types", []):
            parts.append(f"- {incident_type}")
        parts.append("")

    if rep:
        parts += ["### Reporting requirement", ""]
        if rep.get("reportable") == "yes":
            parts.append("- I am including this incident in my final reporting package.")
        elif rep.get("no_new_obligation_identified"):
            parts.append("- **No new reporting obligation identified.** Previously disclosed and unchanged on the user's account; confirm any later change with the security office.")
        else:
            parts.append("- The corpus could not independently confirm the requirement; provide the incident to the appropriate security office for confirmation.")
        if rep.get("timeline"):
            parts.append(f"- Timing: {rep['timeline']}")
        if rep.get("basis"):
            parts.append(f"- Basis: {', '.join(rep['basis'])}")
        parts.append("")

    cw = ev.get("crosswalk") or [] if role in {"applicant", "in_process"} else []
    if cw:
        parts += ["### Form crosswalk — where this goes on the form", ""]
        for c in cw:
            unverified = " *(section unverified — confirm with your FSO)*" if c.get("unverified") else ""
            form_name = {"sf86": "SF-86", "pvq": "PVQ",
                         "incident_report": "Incident Report"}.get(c.get("form"), c.get("form", ""))
            item_text = f", item {c['form_item']}" if c.get("form_item") else ""
            head = f"**{form_name} Section {c.get('form_section')}{item_text} — {c.get('title','')}**{unverified}".strip()
            parts.append(head)
            parts.append("")
            fields = c.get("fields") or []
            for f in fields:
                if isinstance(f, str):
                    parts.append(f"- {f}")
                    continue
                label = f.get("label") or f.get("id", "")
                block = f.get("block")
                loc = f"block {block}" if block else None
                if loc:
                    line = f"- **{label}** *({loc})*"
                elif c.get("form_item"):
                    line = f"- **{label}**"
                else:
                    line = f"- **{label}** *(item location not verified in this corpus — check eApp)*"
                if f.get("question"):
                    line += f"\n  Form asks: “{f['question']}”"
                if f.get("answer"):
                    line += f"\n  Enter: {f['answer']}"
                elif f.get("status"):
                    status_text = {
                        "pending": "Pending — no date exists yet.",
                        "not_applicable": "Not applicable — do not invent a date.",
                        "unknown": "Unknown — obtain or confirm the date before submission.",
                    }.get(f["status"], str(f["status"]).replace("_", " ").title())
                    line += f"\n  Status: {status_text}"
                parts.append(line)
            if fields:
                parts.append("")
            comments_field = c.get("additional_comments_field", True)
            if comments_field:
                note = comments_field if isinstance(comments_field, str) else (
                    "Most SF-86/PVQ sections provide an additional-comments or "
                    "continuation field tied to this kind of entry. "
                    "**Put the narrative statement above in that field** — "
                    "enter the itemized facts above in their own blocks, and "
                    "use the comments field for the explanation in your own "
                    "words. If this section has no comments field, ask your "
                    "FSO where the narrative belongs instead."
                )
                parts.append(f"> {note}")
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

    updates = ev.get("future_update_topics") or []
    if updates:
        parts += ["### Continue updating your security office", ""]
        parts.append(
            "If any of the following later occurs or changes because of this "
            "incident, keep your FSO, security manager, SMO, or sponsoring "
            "security office informed with the pertinent details:"
        )
        parts.append("")
        for update in updates:
            parts.append(f"- {update}")
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
    if events and session.get("final_analysis_complete") is not True:
        print(
            "ERROR: final_analysis_complete is not true. Finish every queued "
            "incident and run the final combined reporting analysis before assembly.",
            file=sys.stderr,
        )
        return 1
    for i, ev in enumerate(events, 1):
        development = ev.get("incident_development")
        if not isinstance(development, dict) or development.get("complete") is not True:
            print(
                f"ERROR: incident {i} has not cleared incident development. "
                "Capture what happened before, during, and after the incident "
                "before narrative assembly."
            )
            return 1

    all_persons: list[dict] = []
    seen = set()
    for ev in events:
        for p in ev.get("persons", []):
            if p["label"] not in seen:
                seen.add(p["label"])
                all_persons.append(p)

    tier = session.get("privacy_tier", "high")
    package_title = {
        "holder": "Adverse Information Incident Report",
        "in_process": "In-Process Applicant Security Update",
        "applicant": "Security Questionnaire Disclosure Package",
    }.get(session.get("role"), "Security Reporting Package")
    doc = [
        f"# {package_title} — John Doe",
        "",
        privacy_header(tier),
        "",
        substitution_block(all_persons, tier),
        PROCEEDING_BOUNDARY,
        "",
        submission_route(session),
        "---",
        "",
    ]
    for i, ev in enumerate(events, 1):
        doc.append(render_event(ev, i, len(events), session.get("role", "applicant")))
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
