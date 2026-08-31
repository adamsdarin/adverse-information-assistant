#!/usr/bin/env python3
"""Deterministic output gate. THIS IS THE TRUST ANCHOR.

Because this tool is model-agnostic, no platform guarantees that an agent
only read /corpus. Prompt-level restrictions are requests, not controls. This
script is the one control that holds regardless of which model produced the
draft, so it runs on every package before delivery and a failure is a hard
stop.

The session file is itself gated: when session.json is provided it is first
run through validate_session.py, so a structurally unsound or tampered state
file fails the package outright — the other checks consume that file and are
only as good as it is.

On PASS the script prints the package's SHA-256 and writes a .sha256 sidecar.
The user runs this script THEMSELVES as the final step and compares the hash,
so delivery does not rest on an assistant's claim that verification passed.

Usage: python scripts/verify_output.py output/package.md [session.json] [--corpus PATH]
Exit 0 = pass, 1 = fail.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import corpus_paths
import library_paths
import validate_session as session_gate

ROOT = Path(__file__).resolve().parent.parent

# PII rules are TIER-AWARE, with two absolutes that no tier can relax:
#   - SSN and date of birth: never, anywhere, at any tier.
#   - Organizations (bar, court, agency, employer, clinic) are exempt at every
#     tier, but an address may only appear if it traces to a CONFIRMED entity
#     record in the session. That is what distinguishes an allowed business
#     address from a disallowed personal one — the string alone cannot.
PERSON_RE = re.compile(r"\bPerson\s+(\d+)\b")
TEMPLATE_HEADING = "Knowledgeable Parties"
ENTITIES_HEADING = "Entities Referenced"

CASE_RE = re.compile(r"ISCR\s+Case\s+No\.?\s*[\d-]+", re.I)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# A DOB LABEL FOLLOWED BY AN ACTUAL DATE. The label alone appears in the
# package's own privacy boilerplate ("no date of birth appears in this
# document"), so matching the phrase would fail every clean package.
DOB_RE = re.compile(
    r"\b(?:date of birth|d\.?o\.?b\.?|born on|born)\b"
    r"(?:\s+(?:is|was|of|on))?\s*[:\-]?\s*"
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{4}-\d{1,2}-\d{1,2}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})",
    re.I,
)
PHONE_RE = re.compile(r"\b(?:\+?1[-. ])?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
# Street-address shape: number + words + street-type token.
ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+(?:[A-Z][\w.'-]*\s+){0,4}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|"
    r"Way|Place|Pl|Terrace|Ter|Highway|Hwy|Parkway|Pkwy)\b\.?",
    re.I,
)

# What each tier permits for NATURAL PERSONS.
TIER_FORBIDS = {
    "low":    {"ssn", "dob"},
    "medium": {"ssn", "dob", "phone", "email", "address"},
    "high":   {"ssn", "dob", "phone", "email", "address", "name"},
}

# Outcome-prediction and advocacy language that must never reach a user.
BANNED = [
    r"\blikely (?:to be )?(?:granted|denied|favorable|unfavorable)\b",
    r"\byour (?:odds|chances)\b",
    r"\bshould be (?:fine|okay|ok)\b",
    r"\bwill probably\b",
    r"\bmost (?:cases|applicants) like\b",
    r"\btypically (?:granted|denied)\b",
    r"\bI (?:recommend|advise) (?:not|against) (?:reporting|disclosing|mentioning)\b",
    r"\byou (?:don't|do not) (?:need|have) to (?:report|disclose|mention)\b",
    r"\bomit\b.{0,30}\bfrom your (?:report|statement)\b",
    r"\bwait until\b.{0,40}\bbefore (?:reporting|telling)\b",
]

REQUIRED_PHRASES = [
    ("no-affiliation disclaimer", "not affiliated"),
    ("adjudication disclaimer", "adjudicative determination"),
    ("pseudonym handoff instruction", "John Doe"),
]

failures: list[str] = []
notes: list[str] = []


def check_tier_declared(session: dict | None) -> str:
    """A package built without a declared tier is verified at the strictest."""
    if not session or not session.get("privacy_tier"):
        notes.append("No privacy_tier in session — verifying at 'high' (strictest)")
        return "high"
    tier = session["privacy_tier"]
    if tier not in TIER_FORBIDS:
        failures.append(f"Unknown privacy_tier {tier!r}")
        return "high"
    if tier == "high" and not session.get("mapping_notice_delivered"):
        failures.append(
            "privacy_tier is 'high' but mapping_notice_delivered is false — the user "
            "is the only record of who Person N is and was never told to write it down"
        )
    return tier


def check_entities(text: str, entities: list[dict]) -> None:
    """Unconfirmed entity addresses must not appear in the package."""
    for e in entities:
        if e.get("confirmed_by_user"):
            continue
        addr = e.get("address")
        if addr and re.sub(r"\s+", " ", str(addr)).strip().lower() in \
                re.sub(r"\s+", " ", text).lower():
            failures.append(
                f"Address for {e.get('name', e.get('label'))!r} appears in the package "
                "but was never confirmed by the user"
            )


def check_persons(text: str) -> None:
    """Person N references must resolve to a blank template entry."""
    referenced = {int(n) for n in PERSON_RE.findall(text)}
    if not referenced:
        return
    if TEMPLATE_HEADING not in text:
        failures.append(
            f"Package references {len(referenced)} knowledgeable part(y/ies) but "
            "ships no completion template — the user has no way to supply them"
        )
        return
    template_section = text.split(TEMPLATE_HEADING, 1)[1]
    for n in sorted(referenced):
        if not re.search(rf"\bPerson\s+{n}\b", template_section):
            failures.append(f"'Person {n}' is referenced but has no template entry")
    # The template must ship BLANK. A filled-in line means the tool collected
    # or generated identity data it was never supposed to touch.
    for label in ("Full name", "Phone number", "Email address", "Mailing address"):
        for line in template_section.splitlines():
            if label in line:
                value = line.split(":", 1)[1] if ":" in line else ""
                if value.strip().strip("_").strip():
                    failures.append(
                        f"Template field {label!r} is pre-filled — the package "
                        "must ship blank for the user to complete by hand"
                    )


CASE_NO_RE = re.compile(r"(\d{2}-\d{4,5})")


def check_citations(text: str, corpus: Path, library: Path | None) -> None:
    """Every cited case must exist in the DCSA Library. This is the primary
    hallucination control.

    Citations resolve against the library's DOHA manifest — the authoritative
    list of every decision actually held. The legacy corpus/doha/index.json is
    still honored if present, for anyone running an older hand-curated corpus.
    If a draft cites a case and NEITHER source is available, that is a failure:
    an unverifiable citation is indistinguishable from a fabricated one.
    """
    cited = {re.sub(r"\s+", " ", m).strip() for m in CASE_RE.findall(text)}
    if not cited:
        return

    known: set[str] = set()
    sources: list[str] = []
    if library is not None:
        try:
            import doha_retrieval
            lib_cases = doha_retrieval.known_case_numbers(library)
            if lib_cases:
                known |= lib_cases
                sources.append(f"DCSA Library ({len(lib_cases)} decisions)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"Could not read the library's DOHA manifest ({e})")

    index_path = corpus / "doha" / "index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            legacy = {str(c.get("case_no", "")) for c in index.get("cases", [])}
            legacy = {m.group(1) for m in
                      (CASE_NO_RE.search(x) for x in legacy) if m}
            if legacy:
                known |= legacy
                sources.append(f"corpus index ({len(legacy)} cases)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"Could not read {index_path} ({e})")

    if not known:
        failures.append(
            "Draft cites decisions but no citation source is available — the "
            "DCSA Library was not found and corpus/doha/index.json holds no "
            "cases. An unverifiable citation is treated as fabricated."
        )
        return

    for c in cited:
        m = CASE_NO_RE.search(c)
        if not m or m.group(1) not in known:
            failures.append(
                f"FABRICATED CITATION: {c!r} does not exist in "
                f"{' or '.join(sources)}"
            )


# ---------------------------------------------------------------------------
# DIRECTIVE QUOTATIONS
# ---------------------------------------------------------------------------
# The section split guarantees a guideline outside the matter never enters the
# context window. It does not guarantee that what gets quoted is what the file
# says. This closes that loop: a quotation attributed to a directive section
# must actually appear in that section's file.
#
# The contract is an attribution line at the end of the blockquote:
#
#     > Conditions that could raise a security concern include...
#     > — SEAD 4, Guideline G
#
# Recognised attributions: SEAD 4 Guideline A-M · SEAD 3 Section A-J or
# Appendix A · ISL 2021-02 Table 1-4.
#
# An unverifiable quotation is treated exactly like an unverifiable case
# citation: as fabricated. If the library is absent, a package that quotes a
# directive does not ship — the honest alternative is not to quote.
ATTRIB = re.compile(
    r"^>\s*[—-]{1,2}\s*(?P<src>SEAD\s*4|SEAD\s*3|ISL\s*2021-02)\s*,\s*"
    r"(?P<part>Guideline\s+[A-M]|Section\s+[A-J]|Appendix\s+[A-C]|Table\s+[1-4])\s*$",
    re.I | re.M)

# The same line with the part left unconstrained. A blockquote signed
# "ISL 2021-02, Table 9" names no part that exists, so the strict pattern does
# not match it — and a check that only inspects what it recognises can be
# stepped around by attributing a passage to a section number that was never
# written. Anything claiming one of these three sources is therefore checked;
# a part this tool cannot resolve is a failure, not a pass.
ATTRIB_LOOSE = re.compile(
    r"^>\s*[—-]{1,2}\s*(?P<src>SEAD\s*4|SEAD\s*3|ISL\s*2021-02)\s*,\s*"
    r"(?P<part>.+?)\s*$", re.I | re.M)


def _sig(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def check_directive_quotes(text: str, library: Path | None) -> None:
    blocks = []
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            current.append(line)
        else:
            if current:
                blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))

    quotes = []
    for b in blocks:
        m = ATTRIB.search(b)
        if not m:
            loose = ATTRIB_LOOSE.search(b)
            if loose:
                failures.append(
                    f"A passage is attributed to {loose.group('src')}, "
                    f"{loose.group('part')} — which is not a part of that "
                    "document this tool can resolve. Cite a real section, or "
                    "do not quote.")
            continue
        body = ATTRIB.sub("", b)
        body = "\n".join(re.sub(r"^>\s?", "", l) for l in body.splitlines())
        if len(_sig(body)) >= 40:
            quotes.append((m.group("src"), m.group("part"), body.strip()))
    if not quotes:
        return

    if library is None:
        failures.append(
            f"Draft quotes {len(quotes)} directive passage(s) but the DCSA "
            "Library is not available, so none can be checked against its "
            "source. An unverifiable quotation is treated as fabricated — "
            "remove the quotes or locate the library.")
        return

    import library_paths as lp
    for src, part, body in quotes:
        src_n = re.sub(r"\s+", "", src).upper()
        kind = part.split()[0].title()
        ident = part.split()[-1].upper()
        paths: list[Path] = []
        if src_n == "SEAD4" and kind == "Guideline":
            paths, _ = lp.guideline_text(library, [ident])
            paths = [x for x in paths if f"Guideline_{ident}_" in x.name]
        else:
            # Every split directive resolves the same way: name -> folder ->
            # manifest -> the one section file that owns this part. Resolve the
            # file through find_ci rather than joining the path directly, or a
            # library whose folder case differs reads as a fabricated quote.
            directive = {"SEAD3": "SEAD-3", "ISL2021-02": "ISL-2021-02"}.get(src_n)
            folder = lp.SPLIT_FOLDERS.get(directive) if directive else None
            manifest = lp.sead_manifest(library, directive) if directive else None
            for sec in (manifest or {}).get("sections", []):
                if kind == "Table":
                    hit = f"Table_{ident}_" in sec["file"]
                elif kind in ("Section", "Appendix"):
                    hit = _matches_part(sec, kind, ident)
                else:
                    hit = False
                if hit:
                    resolved, _ = lp.find_ci(library, f"{folder}/{sec['file']}")
                    if resolved:
                        paths = [resolved]
                    break
        if not paths:
            failures.append(
                f"Draft quotes {src} {part}, but no section file for it was "
                "found in the library. The quotation cannot be checked.")
            continue
        haystack = ""
        for pth in paths:
            try:
                haystack += _sig(pth.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
        if _sig(body) not in haystack:
            failures.append(
                f"A passage attributed to {src} {part} does not appear in that "
                f"section's file. Quoted: {body.strip()[:90]!r}")


def _matches_part(section: dict, kind: str, ident: str) -> bool:
    """Map 'Section F' / 'Appendix A' onto a SEAD-3 section filename."""
    f = section["file"]
    if kind == "Appendix":
        return f"Appendix_{ident}" in f
    return {"F": "02_All_Covered", "G": "03_Secret", "H": "04_Top_Secret",
            "I": "05_Responsibilities", "J": "05_Responsibilities",
            "A": "01_Overview", "B": "01_Overview", "C": "01_Overview",
            "D": "01_Overview", "E": "01_Overview"}.get(ident, "\0") in f


def _entity_allowed(value: str, entities: list[dict]) -> bool:
    """True if this string appears in a confirmed entity record."""
    v = re.sub(r"\s+", " ", value).strip().lower()
    for e in entities:
        if not e.get("confirmed_by_user"):
            continue
        for field in ("address", "phone", "name"):
            ev = e.get(field)
            if ev and (v in re.sub(r"\s+", " ", str(ev)).strip().lower()
                       or re.sub(r"\s+", " ", str(ev)).strip().lower() in v):
                return True
    return False


def check_pii(text: str, tier: str, entities: list[dict]) -> None:
    """Tier-aware. Two things no tier relaxes: SSN and date of birth."""
    forbids = TIER_FORBIDS.get(tier, TIER_FORBIDS["high"])

    # --- absolutes ---------------------------------------------------------
    if SSN_RE.search(text):
        failures.append("SSN pattern in package — never permitted at any privacy tier")
    m = DOB_RE.search(text)
    if m:
        failures.append(
            f"Date-of-birth field in package ({m.group(0)[:40]!r}) — never permitted at "
            "any privacy tier; DOB goes directly on the form"
        )

    # --- tier-dependent, entity-exempt -------------------------------------
    checks = [("phone", PHONE_RE, "phone number"),
              ("email", EMAIL_RE, "email address"),
              ("address", ADDRESS_RE, "street address")]
    for key, rx, label in checks:
        if key not in forbids:
            continue
        for found in {re.sub(r"\s+", " ", x).strip() for x in rx.findall(text)}:
            if _entity_allowed(found, entities):
                continue  # organization data — exempt at every tier
            failures.append(
                f"{label} {found!r} not permitted at privacy tier {tier!r} and does not "
                "match any confirmed entity record"
            )


def check_pseudonym(text: str) -> None:
    if "John Doe" not in text:
        failures.append("Pseudonym 'John Doe' not present — draft may contain a real name")


# Deliberately NOT implemented: detecting whether a capitalized token is a
# person's name. At tier 'high' a name is forbidden, but "Bob" and "Casey's"
# are indistinguishable from ordinary prose by pattern alone, and a regex that
# guessed would produce constant false failures on business names, street
# names, and month names. Structured identifiers (SSN, DOB, phone, email,
# address) are caught reliably; free-text names are not. This is stated in the
# pass message rather than hidden, so nobody mistakes a pass for a guarantee.


def check_banned(text: str) -> None:
    for pattern in BANNED:
        m = re.search(pattern, text, re.I)
        if m:
            failures.append(f"Prohibited language ({pattern}): {m.group(0)!r}")


def check_required(text: str) -> None:
    low = text.lower()
    for label, phrase in REQUIRED_PHRASES:
        if phrase.lower() not in low:
            failures.append(f"Missing {label} (expected text containing {phrase!r})")


def check_version(text: str, corpus: Path) -> None:
    version_file = corpus / "VERSION"
    if not version_file.exists():
        notes.append(f"{version_file} missing; cannot confirm version footer")
        return
    version = version_file.read_text(encoding="utf-8").split()[0]
    if version not in text:
        failures.append(f"Corpus version {version!r} not recorded in the package footer")


def check_outstanding(text: str, session_path: Path | None) -> None:
    """A required field the user never answered must be visible in the package.

    Optional questions may be silently absent — that is honest. Required form
    and reporting fields may not be, because a package that looks finished
    while missing them is the exact failure this tool exists to prevent.
    """
    if not session_path or not session_path.exists():
        return
    session = json.loads(session_path.read_text(encoding="utf-8"))
    outstanding = session.get("outstanding_required", [])
    if not outstanding:
        return
    if "STILL REQUIRED" not in text:
        failures.append(
            f"Session lists {len(outstanding)} unanswered REQUIRED field(s) but the "
            "package has no 'STILL REQUIRED' section — it reads as complete when it is not"
        )
        return
    for item in outstanding:
        el = item.get("element", "")
        if el and el not in text:
            failures.append(f"Required field {el!r} is outstanding but not listed in the package")


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic output gate")
    ap.add_argument("package", help="path to the assembled package.md")
    ap.add_argument("session", nargs="?", help="path to session.json (recommended)")
    ap.add_argument("--corpus", help="corpus root (overrides remembered location)")
    ap.add_argument("--library", help="DCSA Library root (overrides remembered location)")
    args = ap.parse_args()

    path = Path(args.package)
    if not path.exists():
        print(f"ERROR: {path} not found")
        return 1
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(
            "FAIL  package is not UTF-8. It was probably produced with shell "
            "redirection on Windows PowerShell, which writes UTF-16. Re-run "
            "assembly with:  assemble_package.py session.json -o <file>"
        )
        return 1

    corpus = corpus_paths.require(args.corpus)
    library = library_paths.require(args.library)

    session_path = Path(args.session) if args.session else None
    session = None
    if session_path and session_path.exists():
        session = json.loads(session_path.read_text(encoding="utf-8"))
        # Gate the state file itself before trusting anything read from it.
        session_errors, session_warnings = session_gate.validate(session)
        for w in session_warnings:
            notes.append(f"session: {w}")
        for e in session_errors:
            failures.append(f"session: {e}")
    else:
        notes.append(
            "No session.json provided — tier-aware and outstanding-field checks "
            "run at their strictest defaults, and the session file itself was "
            "not validated"
        )
    entities = (session or {}).get("entities", [])
    tier = check_tier_declared(session)
    check_outstanding(text, session_path)

    check_citations(text, corpus, library)
    check_directive_quotes(text, library)
    check_pii(text, tier, entities)
    check_entities(text, entities)
    check_persons(text)
    check_pseudonym(text)
    check_banned(text)
    check_required(text)
    check_version(text, corpus)

    for n in notes:
        print(f"NOTE  {n}")
    for f in failures:
        print(f"FAIL  {f}")

    if failures:
        print(f"\n{len(failures)} failure(s). DO NOT DELIVER THIS PACKAGE.")
        return 1

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")

    print(f"\nPASS — deterministic checks clear (privacy tier: {tier}).")
    print(f"SHA-256 of the verified file: {digest}")
    print(f"(also written to {sidecar.name})")
    print("If an assistant ran this for you, run it yourself and confirm the "
          "hash matches — delivery should not rest on anyone's claim.")
    print("Two things this script CANNOT check, by design:")
    print("  1. Tonal minimization — softening with no factual anchor in the source.")
    print("  2. Whether a capitalized word is a person's name. Structured "
          "identifiers are caught; free-text names are not.")
    print("The user must read the statement themselves before signing it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
