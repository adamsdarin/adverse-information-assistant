#!/usr/bin/env python3
"""Locate and read the DCSA Library. Companion to corpus_paths.py.

Two external things this tool depends on, and they are NOT the same:

  corpus/   — the maintainer's authored analysis (checklists, reporting
              tables, form maps). Small. SHIPS IN THE REPO.
  Library   — the DCSA Library: source documents, DOHA decisions, and
              retrieval indexes. Large. DOWNLOADED SEPARATELY by the user
              and placed wherever they like.

Resolution order (first hit wins):
  1. An explicit --library PATH
  2. The AIA_LIBRARY environment variable
  3. .library-location.json, written by `check_library.py <path> --remember`
  4. A few conventional locations under the user's home

The library declares its own root: any folder containing
START_HERE_FOR_ROBOTS.json is a library root, and every path inside that
file is relative to it. We honor that contract rather than inventing one.

CASE-INSENSITIVE PATH RESOLUTION IS DELIBERATE. The library's own entry
point currently names CATALOG/COLLECTIONS.json while the file on disk is
collections.json. That works on Windows and fails on macOS and Linux. Since
this tool is model- and platform-agnostic, we resolve case-insensitively and
report the mismatch as a fixable warning rather than dying on it.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCATION_FILE = ROOT / ".library-location.json"
ENTRY_POINT = "START_HERE_FOR_ROBOTS.json"

# What each distribution bundle is expected to contain. Paths are relative to
# the library root and resolved case-insensitively.
ESSENTIALS = [
    "START_HERE_FOR_ROBOTS.json",
    "PORTABLE_LIBRARY_INDEX.json",
    "ROBOT_READABLE_DIRECTORY/MANIFESTS/documents.jsonl",
    "ROBOT_READABLE_DIRECTORY/MANIFESTS/DOHA_CURRENT_PATHS.jsonl",
    "ROBOT_READABLE_DIRECTORY/MANIFESTS/DOHA_SEAD4_SEARCH_ROUTER.json",
    "ROBOT_READABLE_DIRECTORY/CATALOG/collections.json",
    "ROBOT_READABLE_DIRECTORY/CATALOG/aliases.json",
]
SEARCH_TIER = [
    "LOCAL_INDEXES/DCSA_DOHA_DECISIONS_FTS.sqlite",
    "LOCAL_INDEXES/DCSA_GENERAL_FTS.sqlite",
]
SOURCE_TIER = ["HUMAN_READABLE_DIRECTORY"]

# ---------------------------------------------------------------------------
# SEAD DIRECTIVE TEXT — SECTION LEVEL
# ---------------------------------------------------------------------------
# The directives are split into one file per section so a reader loads only
# what the matter needs. When a matter implicates Guideline B, the text of
# Guideline L is not in the context window, so it cannot be misattributed. That
# is a physical guarantee rather than an instruction, which makes it the only
# kind that survives a model deciding to be helpful.
#
# Regenerate the split with scripts/split_sead_text.py after a revision.
SEAD_TEXT_DIR = ("ROBOT_READABLE_DIRECTORY/TEXT/PERSONNEL_VETTING/"
                 "SECURITY_EXECUTIVE_AGENT_DIRECTIVES_(SEAD)")
SEAD4_DIR = f"{SEAD_TEXT_DIR}/SEAD-4_Adjudicative-Guidelines"
SEAD3_DIR = f"{SEAD_TEXT_DIR}/SEAD-3_Reporting-Requirements"

# Loaded with EVERY guideline. The adjudicative process and the whole-person
# concept qualify all thirteen; a guideline quoted without them is a fragment
# presented as a rule.
SEAD4_ALWAYS = "02_Appendix_A_Introduction_and_Adjudicative_Process.md"

# SEAD-3 sections F, G and H are ADDITIVE, and not in the way most people
# assume. Section G (Secret/Confidential/L) and Section H (Top Secret/Q) each
# say "in addition to the reporting requirements in Section F" — neither builds
# on the other. So a Top Secret holder gets F + H, NOT F + G + H. Section H
# restates the items it shares with G. Loading G for a TS user would be
# harmless duplication; omitting F for anyone would be a missing obligation.
SEAD3_ALWAYS = ["01_Overview_Policy_and_General_Requirements.md",
                "02_All_Covered_Individuals.md"]
SEAD3_BY_ACCESS = {
    "baseline": "03_Secret_Confidential_L_Noncritical.md",
    "ts_q": "04_Top_Secret_Q_Critical_Special.md",
}
SEAD3_DATA_ELEMENTS = "06_Appendix_A_Required_Data_Elements.md"

# ISL 2021-02 is DCSA's implementation of SEAD 3 for cleared industry, and it
# is the SOURCE OF RECORD for the four reporting tables in
# corpus/reporting/tables/. It lives under INDUSTRIAL_SECURITY, not
# PERSONNEL_VETTING, because it is a DCSA letter rather than an ODNI directive.
#
# The split cuts on the four tables. That matters twice over: an advisor
# answering a foreign-travel question loads Table 4 rather than thirteen pages
# in which Table 1's adverse-information items are also sitting, and the
# maintainer verifying a corpus table gets a file-to-file comparison instead of
# a hunt. Each table section records, in the manifest, the corpus table it is
# source of record for.
ISL_DIR = ("ROBOT_READABLE_DIRECTORY/TEXT/INDUSTRIAL_SECURITY/"
           "INDUSTRIAL_SECURITY_LETTERS_(ISL)/CURRENT")
ISL_FOLDER = "2021-02_SEAD-3_rev-2024"
ISL_SPLIT_DIR = f"{ISL_DIR}/{ISL_FOLDER}"

# Loaded with EVERY table, for the same reason the adjudicative-process
# appendix travels with every guideline: the overview carries the scope, who
# counts as a covered individual, and the adverse-information guidance that the
# tables are read against. A table quoted without it is a list without a rule.
ISL_ALWAYS = "01_Overview_and_Adverse_Information_Guidance.md"

# Directive name -> folder holding its section split and manifest.json. An
# unknown name returns None rather than defaulting to a directive the caller
# did not ask for: a lookup that quietly answers a different question is worse
# than one that fails.
SPLIT_FOLDERS = {
    "SEAD-3": SEAD3_DIR,
    "SEAD-4": SEAD4_DIR,
    "ISL-2021-02": ISL_SPLIT_DIR,
}

# Not distributed to users: maintainer build history, audit trails, migration
# journals. Present in the maintainer's master copy, absent from every bundle.
MAINTAINER_ONLY = ["OPERATIONS", "ARCHIVE"]


def clean_user_path(raw: str) -> Path:
    return Path(str(raw).strip().strip('"').strip("'")).expanduser()


def _candidates() -> list[Path]:
    home = Path.home()
    return [
        home / "Documents" / "DCSA Library",
        home / "DCSA Library",
        home / "Downloads" / "DCSA Library",
        home / "OneDrive" / "Documents" / "DCSA Library",
    ]


def resolve(cli_path: str | None = None) -> tuple[Path | None, str]:
    """Return (library_root, provenance). library_root is None if not found."""
    if cli_path:
        return clean_user_path(cli_path), "--library flag"
    env = os.environ.get("AIA_LIBRARY")
    if env:
        return clean_user_path(env), "AIA_LIBRARY environment variable"
    if LOCATION_FILE.exists():
        try:
            data = json.loads(LOCATION_FILE.read_text(encoding="utf-8"))
            p = data.get("library_path")
            if p:
                return Path(p), f"remembered location ({LOCATION_FILE.name})"
        except Exception:  # noqa: BLE001 — a corrupt memory file falls through
            pass
    for c in _candidates():
        if (c / ENTRY_POINT).is_file():
            return c, "found in a conventional location"
    return None, "not found"


_listing_cache: dict[Path, dict[str, str]] = {}


def _entries(directory: Path) -> dict[str, str] | None:
    """Real on-disk names in `directory`, keyed by lowercase name.

    Cached because the DOHA cases folder holds ~10,658 files and find_ci is
    called repeatedly. Cached for the life of the process only — nothing here
    writes to the library, so the listing cannot go stale under us.
    """
    if directory in _listing_cache:
        return _listing_cache[directory]
    try:
        names = {c.name.lower(): c.name for c in directory.iterdir()}
    except (NotADirectoryError, FileNotFoundError, PermissionError):
        return None
    _listing_cache[directory] = names
    return names


def find_ci(root: Path, relative: str) -> tuple[Path | None, bool]:
    """Resolve a library-relative path, case-insensitively.

    Returns (resolved_path_or_None, exact_case_matched).

    WHY THIS DOES NOT USE Path.exists() TO ESTABLISH EXACT CASE
    -----------------------------------------------------------
    An earlier version asked the filesystem whether the claimed path existed,
    and treated "yes" as proof the case matched. That is true on Linux and macOS
    and FALSE on Windows, where NTFS is case-insensitive: the entry point can
    claim CATALOG/COLLECTIONS.json, the file on disk can be catalog/collections.json,
    and Path.exists() answers True.

    The consequence was not a cosmetic test failure. The whole point of tracking
    `exact` is to warn a maintainer that their library's entry point names paths
    whose case does not match the disk — which is FATAL on macOS and Linux and
    invisible on Windows. So the check silently did nothing on the one platform
    where the maintainer would be building the library, and the warning would
    only ever have fired for the users it was too late to help.

    Comparing against the real directory entries instead is platform-independent:
    iterdir() reports the name as stored, on every filesystem.
    """
    current = root
    exact = True
    for part in relative.replace("\\", "/").split("/"):
        if not part:
            continue
        names = _entries(current)
        if names is None:
            return None, False
        actual = names.get(part.lower())
        if actual is None:
            return None, False
        if actual != part:
            exact = False
        current = current / actual
    return current, exact


def is_library_root(path: Path) -> bool:
    return (path / ENTRY_POINT).is_file() or find_ci(path, ENTRY_POINT)[0] is not None


def detect_tier(root: Path) -> str:
    """Which distribution bundle is present: none | partial | essentials |
    search | complete."""
    have_essentials = all(find_ci(root, p)[0] for p in ESSENTIALS)
    if not have_essentials:
        return "partial" if find_ci(root, ENTRY_POINT)[0] else "none"
    if not all(find_ci(root, p)[0] for p in SEARCH_TIER):
        return "essentials"
    human, _ = find_ci(root, SOURCE_TIER[0])
    if human and human.is_dir() and any(human.rglob("*.pdf")):
        return "complete"
    return "search"


# These describe what a bundle CONTAINS. They previously claimed "real
# guideline text" at every tier while nothing in the tool read any — a
# capability advertised and never wired. Directive text availability is now
# reported separately, from sead_split_status(), because it depends on whether
# the section split has been generated rather than on which bundle was shipped.
TIER_MEANING = {
    "complete": "Full library — decisions, full-text search, and the original "
                "PDFs.",
    "search": "Text and search — everything the tool needs, plus full-text "
              "search across decisions. No source PDFs for human reading.",
    "essentials": "Essentials — the tool works: reporting authorities, case "
                  "metadata and locations. No full-text search across "
                  "decision text.",
    "partial": "INCOMPLETE — the entry point is here but required manifests "
               "are missing. Some grounding is unavailable.",
    "none": "Not a library — no START_HERE_FOR_ROBOTS.json found.",
}


def missing_from(root: Path, items: list[str]) -> list[str]:
    return [p for p in items if not find_ci(root, p)[0]]


def require(cli_path: str | None = None, out=sys.stderr) -> Path | None:
    """Resolve the library, printing provenance. Returns None if absent.

    Absence is NOT fatal — the tool is designed to run without the library and
    say so. Callers decide whether they can proceed.
    """
    path, provenance = resolve(cli_path)
    if path is None:
        print(
            "library: NOT FOUND. The tool will run, but it cannot quote "
            "guideline text or cite any decision.\n"
            "  Run:  python scripts/check_library.py \"<path to DCSA Library>\" --remember",
            file=out,
        )
        return None
    print(f"library: {path}  (from {provenance})", file=out)
    if not is_library_root(path):
        print(
            f"  WARNING: no {ENTRY_POINT} in that folder — it does not look "
            "like the DCSA Library. Treating the library as absent.",
            file=out,
        )
        return None
    return path


def load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


# ---------------------------------------------------------------------------
# SECTION-LEVEL DIRECTIVE LOOKUP
# ---------------------------------------------------------------------------
# These return PATHS, deterministically, from a guideline letter or an access
# tier. Selection is a computation, not a judgement call: an agent asked to
# "find the right file" can pick the wrong one or read the whole directive out
# of convenience, and nothing downstream would notice. Here the caller gets a
# list and reads exactly that list.
def sead_manifest(root: Path, directive: str) -> dict | None:
    """manifest.json for a split directive, or None if the split is absent.

    `directive` is a key of SPLIT_FOLDERS: 'SEAD-3', 'SEAD-4', 'ISL-2021-02'.
    An unrecognised name returns None. It used to fall through to SEAD-4, which
    meant a caller asking for the ISL got the guidelines manifest and no error —
    the quietest possible way to cite the wrong document.
    """
    folder = SPLIT_FOLDERS.get(directive)
    if folder is None:
        return None
    path, _ = find_ci(root, f"{folder}/manifest.json")
    if not path or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def sead_split_status(root: Path) -> dict:
    """What directive text is available, and is it trustworthy?

    Reported separately from the bundle tier because it depends on whether the
    split has been generated — not on which bundle the user downloaded.
    """
    out: dict = {"sead3": False, "sead4": False, "isl": False,
                 "guidelines": [], "isl_tables": [], "problems": []}
    for directive, key in (("SEAD-3", "sead3"), ("SEAD-4", "sead4"),
                           ("ISL-2021-02", "isl")):
        m = sead_manifest(root, directive)
        if not m:
            out["problems"].append(
                f"{directive}: no section split found. Generate it with "
                f"`python scripts/split_sead_text.py \"<library path>\"`.")
            continue
        out[key] = True
        if key == "sead4":
            out["guidelines"] = sorted(x["guideline"] for x in m.get("sections", [])
                                       if "guideline" in x)
            missing = sorted(set("ABCDEFGHIJKLM") - set(out["guidelines"]))
            if missing:
                out["problems"].append(
                    f"SEAD-4 split is incomplete — no file for guideline(s) "
                    f"{', '.join(missing)}. Re-run split_sead_text.py.")
        if key == "isl":
            out["isl_tables"] = sorted(_isl_tables(m))
            missing = sorted({"1", "2", "3", "4"} - set(out["isl_tables"]))
            if missing:
                out["problems"].append(
                    f"ISL 2021-02 split is incomplete — no file for table(s) "
                    f"{', '.join(missing)}. Re-run split_sead_text.py.")
    return out


def _isl_tables(manifest: dict) -> dict[str, str]:
    """Table number -> filename, from the ISL manifest.

    Read from the filename rather than trusting a manifest key, so a manifest
    written by an older version of the splitter still resolves.
    """
    out: dict[str, str] = {}
    for sec in manifest.get("sections", []):
        m = re.search(r"Table_(\d+)_", sec.get("file", ""))
        if m:
            out[m.group(1)] = sec["file"]
    return out


def isl_text(root: Path, tables: list[str] | None = None,
             verifies: list[str] | None = None) -> tuple[list[Path], list[str]]:
    """Paths to read for ISL 2021-02. Returns (paths, problems).

    `tables` are table numbers as strings ('1', '4'). `verifies` are corpus
    table paths — the advisor knows which corpus table matched before it knows
    which ISL table backs it, so it can select by the thing it already has.
    Passing neither returns the whole split, which is the honest answer when
    the caller genuinely does not know yet; passing either narrows it.

    The overview always travels with a table, and a table that is asked for and
    missing is reported rather than substituted.
    """
    m = sead_manifest(root, "ISL-2021-02")
    if not m:
        return [], ["ISL 2021-02 section split not found — run "
                    "split_sead_text.py. Do NOT read the whole letter instead."]
    by_table = _isl_tables(m)
    wanted: list[str] = []
    problems: list[str] = []

    if verifies:
        by_corpus: dict[str, str] = {}
        for sec in m.get("sections", []):
            v = sec.get("verifies")
            if v:
                by_corpus.setdefault(v.replace("\\", "/").lower(), sec["file"])
        for want in verifies:
            key = want.replace("\\", "/").lower()
            hit = by_corpus.get(key) or next(
                (f for c, f in by_corpus.items() if c.endswith(key)), None)
            if hit:
                wanted.append(hit)
            else:
                problems.append(f"no ISL section records itself as the source "
                                f"of record for {want}")
    for t in (tables or []):
        t = str(t).strip()
        if t in by_table:
            wanted.append(by_table[t])
        else:
            problems.append(f"no section file for ISL Table {t}")
    if not tables and not verifies:
        wanted = [sec["file"] for sec in m.get("sections", [])
                  if sec["file"] != ISL_ALWAYS]

    paths: list[Path] = []
    common, _ = find_ci(root, f"{ISL_SPLIT_DIR}/{ISL_ALWAYS}")
    if common:
        paths.append(common)
    else:
        problems.append(f"missing {ISL_ALWAYS} — the tables are read against "
                        "the scope and adverse-information guidance in it")
    seen = set()
    for name in wanted:
        if name in seen:
            continue
        seen.add(name)
        pth, _ = find_ci(root, f"{ISL_SPLIT_DIR}/{name}")
        (paths.append(pth) if pth
         else problems.append(f"{name} listed in the manifest but not on disk"))
    return paths, problems


def guideline_text(root: Path, letters: list[str]) -> tuple[list[Path], list[str]]:
    """Paths to read for the given SEAD 4 guidelines. Returns (paths, problems).

    Always includes the adjudicative-process appendix, because a guideline
    quoted without the whole-person concept is a fragment presented as a rule.
    Returns no path for a letter whose file is missing, and says so — silently
    falling back to the whole directive would defeat the entire point.
    """
    m = sead_manifest(root, "SEAD-4")
    if not m:
        return [], ["SEAD-4 section split not found — run split_sead_text.py. "
                    "Do NOT read the whole directive instead."]
    by_letter = {s["guideline"]: s["file"] for s in m.get("sections", [])
                 if "guideline" in s}
    paths, problems = [], []
    common, _ = find_ci(root, f"{SEAD4_DIR}/{SEAD4_ALWAYS}")
    if common:
        paths.append(common)
    else:
        problems.append(f"missing {SEAD4_ALWAYS} — the adjudicative process and "
                        "whole-person concept qualify every guideline")
    for g in letters:
        g = g.strip().upper()
        if g not in by_letter:
            problems.append(f"no section file for Guideline {g}")
            continue
        p, _ = find_ci(root, f"{SEAD4_DIR}/{by_letter[g]}")
        if p:
            paths.append(p)
        else:
            problems.append(f"Guideline {g} listed in the manifest but not on disk")
    return paths, problems


def reporting_text(root: Path, access: str = "baseline",
                   include_data_elements: bool = True) -> tuple[list[Path], list[str]]:
    """Paths to read for SEAD 3 reporting requirements at a given access tier.

    `access` is 'baseline' (Secret/Confidential/L) or 'ts_q' (Top Secret/Q).
    See SEAD3_BY_ACCESS: the two additive sections are alternatives, not a
    ladder — a Top Secret holder reads F + H, not F + G + H.
    """
    if not sead_manifest(root, "SEAD-3"):
        return [], ["SEAD-3 section split not found — run split_sead_text.py. "
                    "Do NOT read the whole directive instead."]
    wanted = list(SEAD3_ALWAYS)
    extra = SEAD3_BY_ACCESS.get(access)
    if extra:
        wanted.append(extra)
    elif access != "not_applicable":
        return [], [f"unknown access tier {access!r}; expected "
                    f"{sorted(SEAD3_BY_ACCESS)} or 'not_applicable'"]
    if include_data_elements:
        wanted.append(SEAD3_DATA_ELEMENTS)
    paths, problems = [], []
    for name in wanted:
        p, _ = find_ci(root, f"{SEAD3_DIR}/{name}")
        (paths.append(p) if p else problems.append(f"missing {name}"))
    return paths, problems
