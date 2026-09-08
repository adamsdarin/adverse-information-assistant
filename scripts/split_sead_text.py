#!/usr/bin/env python3
"""Split the SEAD-3 and SEAD-4 machine-readable text into per-section files.

WHY THIS EXISTS
---------------
Loading a whole directive to answer a question about one guideline puts twelve
other guidelines in front of the model. Splitting on section boundaries means
that when a matter implicates Guideline B, the text of Guideline L is not in the
context window at all — so it cannot be misattributed. The protection is
physical rather than instructional, which is the only kind that survives a
model that decides to be creative.

WHY IT CUTS ON HEADINGS AND PROVES THE RESULT
---------------------------------------------
An earlier split of these files was cut by size or page offset. The taxonomy was
right and every file was wrong: each one began mid-sentence with the tail of the
previous section. `05_Guideline_C_Foreign_Preference.md` opened with "agency head
or designee;" — the end of a Guideline B mitigating condition. Loading that file
for a foreign-preference matter would have handed the model Guideline B text
labelled as Guideline C, which is worse than reading the whole directive.

Because the boundaries were shifted, the tail of the last file fell off the end
entirely. SEAD-4 lost the Appendix C definitions of waiver, condition and
deviation; SEAD-3 lost part of Appendix A, the sponsoring-agency rule, and the
effective date. Nothing detected any of it.

So this script does two things the previous one did not:

  1. Cuts only at a matched section heading. A file cannot start mid-sentence,
     because the cut point IS the heading.
  2. Proves the parts reassemble into the source. Every non-furniture character
     of the original must appear, in order, across the outputs. If a paragraph
     were dropped the script refuses to write anything.

MAINTAINER TOOL, NOT PART OF A SESSION
--------------------------------------
This is the only script in the repo that writes outside it, and it writes into
the reference library. Nothing in a user session invokes it. Run it by hand when
a new revision of a directive is published, then re-verify.

FAITHFUL TO THE OCR, INCLUDING ITS FLAWS
----------------------------------------
The source is OCR output and carries artifacts: "over120 days", "non-US.",
"DRUG INVOLVEMENT!", a stray "Zh". Those are reproduced exactly. Quietly
correcting a source document is how a corpus stops matching the thing it claims
to quote — normalisation belongs in the tool, where it is visible.

Usage:
  python scripts/split_sead_text.py "<path to DCSA Library>"
  python scripts/split_sead_text.py "<path>" --dry-run    # verify, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import library_paths as lp  # noqa: E402

# WHERE THE SPLIT GOES IS NOT DECIDED HERE.
#
# This script writes the section files and library_paths.py reads them back.
# When each kept its own copy of the folder names, the library rebuild moved
# the directives and only ONE copy was updated — the reader looked in a folder
# the writer had stopped using, and reported the split "absent" while it sat on
# disk. One definition, imported, cannot drift from itself.
SEAD_DIR = lp.SEAD_TEXT_DIR
ISL_DIR = lp.ISL_DIR

# Page furniture. Removed from the output and excluded from the reassembly
# comparison, so stripping it can never hide a real omission.
FURNITURE = re.compile(
    r"^\s*(?:=+\s*PAGE\s+\d+\s*=+|UNCLASSIFIED|Page\s+\d+|\d{1,3})\s*$", re.I)

# ---------------------------------------------------------------------------
# Section anchors. Each entry: (regex, output filename, human title, scope).
# The regex must match the FIRST LINE of the section, anchored at line start.
# ---------------------------------------------------------------------------
SEAD3 = [
    (r"^A\.\s+AUTHORITY", "01_Overview_Policy_and_General_Requirements.md",
     "Overview, Policy and General Requirements",
     "Authority, purpose, applicability, definitions and policy."),
    (r"^F\.\s+REPORTABLE ACTIVITIES FOR ALL COVERED INDIVIDUALS",
     "02_All_Covered_Individuals.md", "All Covered Individuals",
     "Reportable activities that apply to every covered individual."),
    (r"^G\.\s+REPORTABLE ACTIVITIES FOR INDIVIDUALS WITH ACCESS TO SECRET",
     "03_Secret_Confidential_L_Noncritical.md",
     "Secret, Confidential, L Access, and Non-Critical Sensitive Positions",
     "Additional reporting requirements at the Secret/Confidential/L level, "
     "in addition to those in Section F."),
    (r"^H\.\s+REPORTABLE ACTIVITIES FOR INDIVIDUALS WITH ACCESS TO TOP SECRET",
     "04_Top_Secret_Q_Critical_Special.md",
     "Top Secret, Q Access, and Critical or Special Sensitive Positions",
     "Additional reporting requirements at the Top Secret/Q level, in addition "
     "to those in Section F."),
    (r"^I\.\s+RESPONSIBILITIES", "05_Responsibilities_and_Effective_Date.md",
     "Responsibilities and Effective Date",
     "Agency responsibilities and the effective date of the Directive."),
    (r"^APPENDIX A", "06_Appendix_A_Required_Data_Elements.md",
     "Appendix A — Required Data Elements for Reporting",
     "The information a report must contain, by reportable activity."),
]

GUIDELINES = [
    ("A", "Allegiance_to_the_United_States", "Allegiance to the United States"),
    ("B", "Foreign_Influence", "Foreign Influence"),
    ("C", "Foreign_Preference", "Foreign Preference"),
    ("D", "Sexual_Behavior", "Sexual Behavior"),
    ("E", "Personal_Conduct", "Personal Conduct"),
    ("F", "Financial_Considerations", "Financial Considerations"),
    ("G", "Alcohol_Consumption", "Alcohol Consumption"),
    ("H", "Drug_Involvement_and_Substance_Misuse",
     "Drug Involvement and Substance Misuse"),
    ("I", "Psychological_Conditions", "Psychological Conditions"),
    ("J", "Criminal_Conduct", "Criminal Conduct"),
    ("K", "Handling_Protected_Information", "Handling Protected Information"),
    ("L", "Outside_Activities", "Outside Activities"),
    ("M", "Use_of_Information_Technology", "Use of Information Technology"),
]

SEAD4 = [
    (r"^A\.\s+AUTHORITY", "01_Directive_Overview_and_Policy.md",
     "Directive Overview and Policy",
     "Authority, purpose, applicability, definitions, policy and effective date."),
    (r"^APPENDIX A\b", "02_Appendix_A_Introduction_and_Adjudicative_Process.md",
     "Appendix A — Introduction and the Adjudicative Process",
     "The introduction and the adjudicative process, including the whole-person "
     "concept. APPLIES TO EVERY GUIDELINE — load this alongside any guideline."),
]
for _i, (_ltr, _slug, _title) in enumerate(GUIDELINES, start=3):
    SEAD4.append((rf"^GUIDELINE {_ltr}:", f"{_i:02d}_Guideline_{_ltr}_{_slug}.md",
                  f"Guideline {_ltr} — {_title}",
                  f"The concern, disqualifying conditions and mitigating "
                  f"conditions for Guideline {_ltr}."))
SEAD4 += [
    (r"^APPENDIX B\b", "16_Appendix_B_Bond_Amendment_Guidance.md",
     "Appendix B — Bond Amendment Guidance",
     "Statutory restrictions on granting eligibility."),
    (r"^APPENDIX C\b", "17_Appendix_C_Exceptions.md",
     "Appendix C — Exceptions",
     "Waiver, condition and deviation — definitions and when each applies."),
]

PROVENANCE = (
    "> Section-level extract of the machine-readable text of *{full}*. Cut at "
    "section headings by `scripts/split_sead_text.py`; the parts are verified "
    "to reassemble into the source. Page and classification furniture is "
    "removed. OCR artifacts in the source are reproduced unchanged — this file "
    "is faithful to the text it was made from, not corrected."
)

# The ISL's four tables are the source of record for the four reporting tables
# in corpus/reporting/tables/. Splitting on them means the requirements advisor
# loads one table's text rather than the whole letter — and it makes the
# maintainer's verification pass a file-to-file comparison instead of a hunt
# through thirteen pages. `verifies` records that pairing in the manifest.
ISL = [
    (r"^\s*CLARIFICATION AND GUIDANCE ON REPORTABLE ACTIVITIES",
     "01_Overview_and_Adverse_Information_Guidance.md",
     "Overview and Adverse Information Guidance",
     "Scope, who counts as a covered individual, and the narrative guidance on "
     "adverse information reporting that precedes the tables.", None),
    (r"^\s*TABLE 1:", "02_Table_1_Adverse_Information.md",
     "Table 1 — Adverse Information Reporting Requirements",
     "Adverse information items reportable for all covered individuals.",
     "corpus/reporting/tables/adverse-information.yaml"),
    (r"^\s*TABLE 2:", "03_Table_2_All_Covered_Individuals.md",
     "Table 2 — Reporting Requirements for All Covered Individuals",
     "Reportable activities that apply to every covered individual.",
     "corpus/reporting/tables/all-covered-individuals.yaml"),
    (r"^\s*TABLE 3:", "04_Table_3_Top_Secret_Q.md",
     "Table 3 — Top Secret and \u201cQ\u201d Access",
     "Additional reporting requirements specific to Top Secret or Q access.",
     "corpus/reporting/tables/top-secret-q.yaml"),
    (r"^\s*TABLE 4:", "05_Table_4_Foreign_Travel.md",
     "Table 4 — Foreign Travel Reporting",
     "Foreign travel reporting, pre-approval, and the aggregation rule.",
     "corpus/reporting/tables/all-covered-individuals.yaml"),
]

DIRECTIVES = {
    "SEAD-3": {
        "full": "Security Executive Agent Directive 3: Reporting Requirements "
                "for Personnel with Access to Classified Information or Who "
                "Hold a Sensitive Position",
        "anchors": SEAD3,
    },
    "SEAD-4": {
        "full": "Security Executive Agent Directive 4: National Security "
                "Adjudicative Guidelines",
        "anchors": SEAD4,
    },
    "ISL-2021-02": {
        "full": "DCSA Industrial Security Letter 2021-02, SEAD 3 "
                "implementation for cleared industry (revised 2024)",
        "anchors": ISL,
    },
}


def strip_furniture(lines: list[str]) -> list[str]:
    return [l for l in lines if not FURNITURE.match(l)]


def sig(text: str) -> str:
    """Comparison form: letters and digits only. Immune to whitespace, line
    wrapping and the markdown headers the outputs add."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def split_one(name: str, spec: dict, root: Path, dry: bool) -> tuple[bool, list[str]]:
    log: list[str] = []
    src, provenance = lp.directive_source(root, name)
    if src is None:
        return False, [
            f"source text for {name} not found in the library.",
            f"  Looked up document_id {lp.DIRECTIVE_DOC_IDS.get(name)!r} in "
            f"{lp.DOCUMENTS_MANIFEST},",
            f"  then tried {lp.DIRECTIVE_FALLBACK_TEXT.get(name)}."]
    log.append(f"{name}: source {src.name} (via {provenance})")
    raw = src.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    # ---- locate every anchor, and insist each matches exactly once ---------
    cuts: list[tuple[int, tuple]] = []
    for anchor in spec["anchors"]:
        pat = re.compile(anchor[0])
        hits = [i for i, l in enumerate(lines) if pat.match(l)]
        if len(hits) != 1:
            return False, [f"{name}: anchor {anchor[0]!r} matched {len(hits)} "
                           f"times; expected exactly 1"]
        cuts.append((hits[0], anchor))
    cuts.sort(key=lambda c: c[0])
    if [c[1][1] for c in cuts] != [a[1] for a in spec["anchors"]]:
        return False, [f"{name}: sections are not in the expected order"]

    # ---- slice; the preamble before the first heading joins section 1 ------
    pieces = []
    for n, (start, anchor) in enumerate(cuts):
        end = cuts[n + 1][0] if n + 1 < len(cuts) else len(lines)
        body = lines[0:end] if n == 0 else lines[start:end]
        pieces.append((anchor, strip_furniture(body)))

    # ---- PROOF: the parts must reassemble into the source ------------------
    want = sig("\n".join(strip_furniture(lines)))
    got = sig("\n".join("\n".join(b) for _, b in pieces))
    if want != got:
        # Locate the first divergence so the failure is actionable.
        i = next((k for k in range(min(len(want), len(got))) if want[k] != got[k]),
                 min(len(want), len(got)))
        return False, [
            f"{name}: REASSEMBLY FAILED — the parts do not reproduce the source.",
            f"  source {len(want)} chars, parts {len(got)} chars",
            f"  first divergence at char {i}: source …{want[max(0,i-60):i+60]}…",
            f"                                parts  …{got[max(0,i-60):i+60]}…",
            "  Nothing was written."]
    log.append(f"{name}: reassembly verified — {len(want):,} characters, "
               f"{len(pieces)} sections, no loss")

    # ---- each section must begin at its own heading ------------------------
    for anchor, body in pieces:
        first = next((l for l in body if l.strip()), "")
        if anchor is cuts[0][1]:
            continue  # section 1 legitimately opens with the title block
        if not re.match(anchor[0], first):
            return False, [f"{name}: {anchor[1]} does not start at its heading "
                           f"(starts {first[:60]!r})"]
    log.append(f"{name}: every section starts at its own heading")

    if name == "SEAD-4":
        letters = {re.search(r"Guideline_([A-M])_", a[1]).group(1)
                   for a, _ in pieces if "_Guideline_" in a[1]}
        missing = sorted(set("ABCDEFGHIJKLM") - letters)
        if missing:
            return False, [f"SEAD-4: missing guideline file(s) for {missing}"]
        log.append("SEAD-4: all 13 guidelines A–M present, one file each")

    if dry:
        log.append(f"{name}: dry run — nothing written")
        return True, log

    # ---- write ------------------------------------------------------------
    out = root / lp.SPLIT_FOLDERS[name]
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"directive": name, "source_file": src.name,
                "source_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "generated_by": "scripts/split_sead_text.py",
                "cut_method": "section headings, reassembly-verified",
                "sections": []}
    for anchor, body in pieces:
        pat, fname, title, scope = anchor[:4]
        verifies = anchor[4] if len(anchor) > 4 else None
        text = "\n".join(body).strip("\n")
        doc = (f"# {name} — {title}\n\n**Scope:** {scope}\n\n"
               f"{PROVENANCE.format(full=spec['full'])}\n\n---\n\n{text}\n")
        (out / fname).write_text(doc, encoding="utf-8")
        entry = {"file": fname, "title": title,
                 "body_sha256": hashlib.sha256(text.encode()).hexdigest(),
                 "lines": len(body)}
        m = re.search(r"Guideline_([A-M])_", fname)
        if m:
            entry["guideline"] = m.group(1)
        if verifies:
            entry["verifies"] = verifies
        manifest["sections"].append(entry)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                       encoding="utf-8")

    index = "\n".join(f"| `{s['file']}` | {s['title']} |"
                      for s in manifest["sections"])
    (out / "README.md").write_text(
        f"# {name} — section-level text\n\n"
        f"Machine-readable text of *{spec['full']}*, split so a reader loads "
        f"only the section it needs.\n\n"
        f"Cut at section headings and verified to reassemble into "
        f"`../{src.name}` with no loss. `manifest.json` carries the "
        f"section index and a SHA-256 for each body.\n\n"
        + ("**Load `02_Appendix_A_Introduction_and_Adjudicative_Process.md` "
           "alongside any guideline file.** It carries the adjudicative process "
           "and the whole-person concept, which qualify every guideline.\n\n"
           if name == "SEAD-4" else
           "**Sections G and H are additive.** They list requirements *in "
           "addition to* Section F, so a reader at either level needs "
           "`02_All_Covered_Individuals.md` as well.\n\n"
           if name == "SEAD-3" else
           "Each table file records, in `manifest.json`, the corpus reporting "
           "table it is the source of record for — so verifying a corpus table "
           "is a file-to-file comparison rather than a hunt through the "
           "letter.\n\n")
        + f"| File | Contents |\n|---|---|\n{index}\n\n"
        f"Regenerate with `python scripts/split_sead_text.py \"<library path>\"`.\n",
        encoding="utf-8")
    log.append(f"{name}: wrote {len(pieces)} sections + manifest.json + README.md "
               f"to {out.name}/")
    return True, log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("library", type=Path, help="path to the DCSA Library folder")
    ap.add_argument("--dry-run", action="store_true",
                    help="verify and report, write nothing")
    args = ap.parse_args()

    ok_all = True
    for name, spec in DIRECTIVES.items():
        ok, log = split_one(name, spec, args.library, args.dry_run)
        for line in log:
            print(("  " if ok else "  ERROR ") + line)
        print()
        ok_all &= ok
    if not ok_all:
        print("FAILED — nothing was written for the directive(s) reported above.")
        return 1
    print("All sections verified against their source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
