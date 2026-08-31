#!/usr/bin/env python3
"""Regression tests for the deterministic scripts.

These scripts are the trust anchor: because the tool is model-agnostic,
nothing except them enforces that output is safe to hand a security officer.
Which means an unnoticed regression in a regex here silently removes the only
real control in the system.

Plain Python — no pytest, no test framework to install. A maintainer who is
not a developer runs one command.

Usage:  python tests/run_tests.py
Exit:   0 all passed · 1 something failed
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

# Windows terminals may default to cp1252, while test names intentionally use
# symbols such as arrows. Keep the safety suite runnable regardless of the
# active console code page; this changes display encoding only.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
ASSEMBLE = ROOT / "scripts" / "assemble_package.py"
VERIFY = ROOT / "scripts" / "verify_output.py"
VALSESS = ROOT / "scripts" / "validate_session.py"
SCORE = ROOT / "scripts" / "score_evals.py"
CHECKLIB = ROOT / "scripts" / "check_library.py"
RETRIEVAL = ROOT / "scripts" / "doha_retrieval.py"
COURTS = ROOT / "scripts" / "court_lookup.py"
VALIDATE = ROOT / "scripts" / "validate_corpus.py"

# Drift check: conductor.md is the generative source of the session flow and
# PROCESS.md renders it. These two anchor lists encode the SAME canonical
# stage order, expressed in each file's own vocabulary. If either file
# reorders or drops a stage, its anchors stop appearing in this order and the
# check fails — forcing whoever edits one file to look at the other.
CONDUCTOR_ANCHORS = [
    "**Locate the reference material**", "**Capability canary", "**Intake**", "**Triage",
    "**Internal requirements routing", "**Adjudicative criteria**",
    "**Question sourcing", "**Gap loop**", "**Incident detection and queueing",
    "**Consistency**", "**Documents**", "**Narrative**", "**Invisible candor pass**",
    "**Final combined reporting analysis",
    "**Assemble**", "**Verify**", "**Handoff**",
]
PROCESS_ANCHORS = [
    "0 · Locate reference material", "0b · Capability canary",
    "1 · Intake", "<b>Open narrative</b>", "① Internal requirements routing",
    "② Classifier", "<b>Question sourcing</b>",
    "<b>Gap → Interview loop</b>", "<b>Incident Detector</b>",
    "<b>Consistency Checker</b>", "<b>Documents Advisor</b>",
    "<b>Narrative Writer</b>", "<b>Invisible Candor Reviewer</b>",
    "<b>Final combined reporting analysis</b>",
    "<b>Deterministic gates</b>", "<b>Handoff</b>",
]


def check_anchor_order(path: Path, anchors: list[str]) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8")
    last = -1
    for a in anchors:
        i = text.find(a)
        if i == -1:
            return False, f"anchor {a!r} missing from {path.name}"
        if i <= last:
            return False, f"anchor {a!r} out of order in {path.name}"
        last = i
    return True, ""

passed, failed = 0, 0


def run(script: Path, *args: str, env: dict | None = None) -> tuple[int, str]:
    full_env = {**os.environ, **env} if env else None
    r = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, env=full_env)
    return r.returncode, r.stdout + r.stderr


def run_json(script: Path, *args: str) -> tuple[int, dict, str]:
    """For scripts that emit JSON on stdout. Provenance lines go to stderr by
    design, so they must not be merged in before parsing."""
    r = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True)
    try:
        data = json.loads(r.stdout[r.stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        data = {}
    return r.returncode, data, r.stdout + r.stderr


def flatten(text: str) -> str:
    """Collapse a hard-wrapped prompt to one line for substring checks.

    Agent prompts wrap at ~76 chars and quote example dialogue with '> ',
    so a phrase the reader sees as contiguous is split across lines and
    peppered with blockquote markers. Strip both before comparing.
    """
    lines = [l.lstrip().removeprefix("> ").removeprefix(">") for l in text.splitlines()]
    return " ".join(" ".join(lines).split())


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def base_session() -> dict:
    return {
        "privacy_tier": "high",
        "mapping_notice_delivered": True,
        "form": "sf86",
        "population": "industry",
        "role": "holder",
        "final_analysis_complete": True,
        "entities": [{
            "label": "Entity 1", "type": "business_or_venue",
            "name": "The Blue Heron Tavern",
            "address": "1 Fictional Way, Testville, XX 00000",
            "phone": None, "source": "user_confirmed_lookup",
            "confirmed_by_user": True, "needs_user_supply": False,
        }],
        "events": [{
            "title": "Alcohol-related arrest",
            "guidelines": ["G", "J"],
            "incident_development": {
                "profiles": ["impaired-driving", "arrest-or-criminal-process", "substance-use-or-treatment"],
                "complete": True,
                "phases": {
                    "before": {"status": "answered", "evidence": "I was at The Blue Heron Tavern before driving."},
                    "precipitating_circumstances": {"status": "answered", "evidence": "I drank alcohol before deciding to drive."},
                    "decisions_and_actions": {"status": "answered", "evidence": "I left the tavern and drove."},
                    "incident": {"status": "answered", "evidence": "I was stopped and arrested for OWI."},
                    "immediate_aftermath": {"status": "answered", "evidence": "A breath test reported 0.16."},
                    "later_consequences": {"status": "answered", "evidence": "A criminal court matter followed."},
                    "current_status": {"status": "answered", "evidence": "The incident is being reported."},
                    "future_developments": {"status": "answered", "evidence": "The court disposition may follow later."},
                },
            },
            "incident_types": ["Alcohol Consumption", "Criminal Conduct"],
            "future_update_topics": [
                "Any later court disposition or change in charges",
                "Any alcohol evaluation, counseling, or treatment later ordered, started, changed, completed, or not completed",
            ],
            "narrative": (
                "I was arrested on 3 March 2026 for operating while intoxicated after "
                "leaving The Blue Heron Tavern, 1 Fictional Way, Testville, XX 00000. "
                "My blood alcohol level was 0.16. Person 1, my supervisor, was informed "
                "the following week. Person 2, my spouse, knew that night."
            ),
            "reporting": {"reportable": "yes", "channel": "FSO -> DISS incident report",
                          "timeline": "promptly", "basis": ["aci.criminal.arrest"],
                          "voluntary": False},
            "crosswalk": [{"form_section": "22", "title": "Police Record"}],
            "documents": [{"name": "Certified court disposition",
                           "source": "Clerk of court", "timing": "can_follow"}],
            "persons": [{"label": "Person 1", "role": "my supervisor"},
                        {"label": "Person 2", "role": "my spouse"}],
            "declined_elements": ["current-relationship"],
        }],
    }


def build(session: dict, tmp: Path) -> tuple[Path, Path]:
    sp = tmp / "session.json"
    sp.write_text(json.dumps(session), encoding="utf-8")
    pkg = tmp / "package.md"
    code, out = run(ASSEMBLE, str(sp), "-o", str(pkg))
    if code != 0 or not pkg.exists():
        print(f"  FATAL assemble failed:\n{out}")
        sys.exit(1)
    return pkg, sp


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        print("\nassemble_package.py")
        pkg, sp = build(base_session(), tmp)
        text = pkg.read_text(encoding="utf-8")
        check("emits the disclaimer", "not affiliated" in text.lower())
        check("emits the adjudication disclaimer", "adjudicative determination" in text.lower())
        check("emits the corpus version", "0.1.0" in text)
        check("emits a blank Person template", "Knowledgeable Parties" in text and "Full name: __" in text)
        check("template ships blank", "Full name: Jane" not in text)
        check("lists declined elements rather than filling them",
              "Not addressed" in text and "nothing significant" not in text)
        check("holder output lists multiple DISS types under one incident",
              "Applicable DISS incident type(s)" in text
              and "Alcohol Consumption" in text and "Criminal Conduct" in text
              and text.count("## Incident 1 of 1") == 1)
        check("holder output suppresses applicant form crosswalks",
              "Form crosswalk" not in text)
        check("holder output carries a tailored future-update notice",
              "Continue updating your security office" in text
              and "later court disposition" in text)
        check("package carries the separate-proceeding limitation",
              "cannot determine how a security report may interact" in flatten(text)
              and "discoverability" in flatten(text))

        applicant = base_session()
        applicant["role"] = "applicant"
        applicant["events"][0].pop("incident_types")
        applicant_pkg, _ = build(applicant, tmp)
        applicant_text = applicant_pkg.read_text(encoding="utf-8")
        check("initial applicant output routes to the form",
              "initial SF-86 or PVQ" in applicant_text
              and "Form crosswalk" in applicant_text
              and "Applicable DISS incident type(s)" not in applicant_text)

        in_process = base_session()
        in_process["role"] = "in_process"
        in_process["events"][0].pop("incident_types")
        in_process_pkg, _ = build(in_process, tmp)
        in_process_text = in_process_pkg.read_text(encoding="utf-8")
        check("in-process output routes through the sponsoring office",
              "SMO or security office sponsoring" in in_process_text
              and "initial investigation" in in_process_text
              and "Form crosswalk" in in_process_text)

        incomplete = base_session()
        incomplete["final_analysis_complete"] = False
        incomplete_path = tmp / "incomplete.json"
        incomplete_out = tmp / "incomplete.md"
        incomplete_path.write_text(json.dumps(incomplete), encoding="utf-8")
        c, o = run(ASSEMBLE, str(incomplete_path), "-o", str(incomplete_out))
        check("assembly waits for the final combined analysis",
              c == 1 and "final_analysis_complete" in o)

        undeveloped = base_session()
        undeveloped["events"][0].pop("incident_development")
        undeveloped_path = tmp / "undeveloped.json"
        undeveloped_out = tmp / "undeveloped.md"
        undeveloped_path.write_text(json.dumps(undeveloped), encoding="utf-8")
        c, o = run(ASSEMBLE, str(undeveloped_path), "-o", str(undeveloped_out))
        check("assembly refuses an incident with no before/during/after development",
              c == 1 and "incident development" in o.lower())

        print("\nverify_output.py — clean package")
        code, out = run(VERIFY, str(pkg), str(sp))
        check("clean package passes", code == 0, out.strip()[-300:])
        check("pass prints the package SHA-256", "sha-256" in out.lower())
        check("pass writes a .sha256 sidecar", (tmp / "package.md.sha256").exists())

        print("\nverify_output.py — planted defects must FAIL")

        def mutate(fn, label, session=None, expect_in=None):
            t = pkg.read_text(encoding="utf-8")
            bad = tmp / "bad.md"
            bad.write_text(fn(t), encoding="utf-8")
            s = sp
            if session is not None:
                s = tmp / "bad.json"
                s.write_text(json.dumps(session), encoding="utf-8")
            c, o = run(VERIFY, str(bad), str(s))
            ok = c == 1 and (expect_in is None or expect_in.lower() in o.lower())
            check(label, ok, o.strip()[-300:])

        mutate(lambda t: t.replace("ISCR", "x") + "\nSee ISCR Case No. 23-99999.\n",
               "fabricated case citation", expect_in="fabricated")
        mutate(lambda t: t.replace("Person 2, my spouse, knew that night.",
                                   "Reach my spouse at 555-867-5309."),
               "phone number at tier high", expect_in="phone")
        mutate(lambda t: t.replace("My blood alcohol level was 0.16.",
                                   "My date of birth is 04/12/1988."),
               "date of birth in prose", expect_in="date-of-birth")
        mutate(lambda t: t.replace("- How they know: my supervisor",
                                   "- How they know: my supervisor\n- DOB: 4/12/1988"),
               "date of birth as a labeled field", expect_in="date-of-birth")
        mutate(lambda t: t.replace("Full name: ________________________________",
                                   "Full name: Jane Smith", 1),
               "pre-filled template field", expect_in="pre-filled")
        mutate(lambda t: t.replace("Person 2, my spouse, knew that night.",
                                   "Person 2 and Person 3 knew that night."),
               "Person N with no template entry", expect_in="person 3")
        mutate(lambda t: t + "\nYour case should be fine.\n",
               "outcome-prediction language", expect_in="prohibited")
        mutate(lambda t: t + "\nYou do not have to report the drinking.\n",
               "concealment language", expect_in="prohibited")
        mutate(lambda t: t.replace("not affiliated", "affiliated with"),
               "missing no-affiliation disclaimer", expect_in="disclaimer")
        mutate(lambda t: t.replace("Person 1, my supervisor, was informed",
                                   "Person 1 lives at 900 Oak Avenue and was informed"),
               "personal address matching no entity record", expect_in="address")

        print("\nverify_output.py — tier and session interactions")
        s = base_session(); s["privacy_tier"] = "medium"
        sm = tmp / "med.json"; sm.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VERIFY, str(pkg), str(sm))
        check("business address still allowed at tier medium", c == 0, o.strip()[-300:])

        s = base_session(); s["mapping_notice_delivered"] = False
        sn = tmp / "nomap.json"; sn.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VERIFY, str(pkg), str(sn))
        check("tier high without mapping notice fails", c == 1 and "mapping" in o.lower())

        s = base_session()
        s["outstanding_required"] = [{"element": "court_name",
                                      "source_ref": "PVQ Section 11",
                                      "how_to_get": "Clerk of court"}]
        pkg2, sp2 = build(s, tmp)
        c, o = run(VERIFY, str(pkg2), str(sp2))
        check("outstanding required fields surface in the package", c == 0, o.strip()[-300:])
        check("STILL REQUIRED section present", "STILL REQUIRED" in pkg2.read_text(encoding="utf-8"))

        stripped = tmp / "stripped.md"
        stripped.write_text("\n".join(
            l for l in pkg2.read_text(encoding="utf-8").split("\n")
            if "STILL REQUIRED" not in l and "court_name" not in l), encoding="utf-8")
        c, o = run(VERIFY, str(stripped), str(sp2))
        check("hiding an outstanding required field fails", c == 1 and "required" in o.lower())

        print("\nverify_output.py — voluntary disclosure")
        s = base_session()
        s["events"][0]["reporting"]["voluntary"] = True
        pkg3, sp3 = build(s, tmp)
        check("voluntary disclosure is marked in the package",
              "voluntar" in pkg3.read_text(encoding="utf-8").lower(),
              "voluntary=true produced no visible marking")

        print("\nvalidate_session.py — the state file is gated too")

        def vs(session: dict, name: str, *flags: str) -> tuple[int, str]:
            p = tmp / name
            p.write_text(json.dumps(session), encoding="utf-8")
            return run(VALSESS, str(p), *flags)

        c, o = vs(base_session(), "vs-clean.json")
        check("sound session passes", c == 0, o.strip()[-300:])

        s = base_session()
        s["events"][0].pop("incident_development")
        c, o = vs(s, "vs-no-development.json")
        check("final analysis requires a gated incident-development record",
              c == 1 and "incident_development" in o, o.strip()[-300:])

        s = base_session()
        s["events"][0]["incident_development"]["phases"].pop("before")
        c, o = vs(s, "vs-missing-before.json")
        check("incident development requires what happened beforehand",
              c == 1 and "missing phases" in o.lower() and "before" in o,
              o.strip()[-300:])

        s = base_session()
        s["events"][0]["incident_development"]["profiles"] = ["invented-profile"]
        c, o = vs(s, "vs-unknown-profile.json")
        check("incident development rejects invented profile names",
              c == 1 and "unknown incident-development profiles" in o.lower(),
              o.strip()[-300:])

        s = base_session()
        phase = s["events"][0]["incident_development"]["phases"]["current_status"]
        phase.update({"status": "unknown", "evidence": "The current status is not yet known."})
        c, o = vs(s, "vs-hidden-unknown.json")
        check("unknown chronology facts cannot disappear from the report state",
              c == 1 and "outstanding_required" in o, o.strip()[-300:])

        s["outstanding_required"] = [{
            "element": "incident_development.current_status",
            "source_ref": "incident chronology",
            "how_to_get": "Confirm the current status with the responsible office.",
        }]
        c, o = vs(s, "vs-surfaced-unknown.json")
        check("a surfaced unknown chronology fact may proceed as still required",
              c == 0, o.strip()[-300:])

        s = base_session()
        s["role"] = "in_process"
        s["events"][0].pop("incident_types")
        c, o = vs(s, "vs-in-process.json")
        check("in_process is a valid status with form-oriented incidents",
              c == 0, o.strip()[-300:])

        s = base_session()
        s["events"][0]["incident_types"] = ["Made Up DISS Type"]
        c, o = vs(s, "vs-bad-diss-type.json")
        check("unknown DISS incident types are rejected",
              c == 1 and "unknown diss incident type" in o.lower(), o.strip()[-300:])

        s = base_session()
        s["events"][0].pop("incident_types")
        c, o = vs(s, "vs-holder-no-diss-type.json")
        check("completed holder incidents require a DISS type",
              c == 1 and "needs at least one" in o.lower(), o.strip()[-300:])

        s = base_session()
        s["role"] = "applicant"
        s["events"][0].pop("incident_types")
        s["events"][0]["crosswalk"][0]["fields"] = [{
            "id": "disposition_date", "label": "Disposition date",
            "answer": "Not yet resolved.",
        }]
        c, o = vs(s, "vs-date-status.json")
        check("a status cannot be entered in a date field",
              c == 1 and "date field" in o.lower() and "status" in o.lower(),
              o.strip()[-300:])

        s = base_session()
        s["role"] = "applicant"
        s["events"][0].pop("incident_types")
        s["events"][0]["crosswalk"][0]["fields"] = [{
            "id": "disposition_date", "label": "Disposition date",
            "status": "pending",
        }]
        c, o = vs(s, "vs-pending-date.json")
        check("a pending date is represented structurally", c == 0, o.strip()[-300:])
        pending_pkg, _ = build(s, tmp)
        pending_text = pending_pkg.read_text(encoding="utf-8")
        check("renderer explains a pending date without an Enter value",
              "Status: Pending — no date exists yet." in pending_text and
              "Enter: Not yet resolved" not in pending_text)

        s = base_session()
        s["role"] = "applicant"
        s["events"][0].pop("incident_types")
        s["events"][0]["crosswalk"][0].update({
            "form": "sf86", "form_item": "22.1",
            "fields": [{"id": "disposition_date", "label": "Disposition date",
                        "status": "pending"}],
        })
        item_pkg, _ = build(s, tmp)
        item_text = item_pkg.read_text(encoding="utf-8")
        check("renderer states a known form item once in the heading",
              "Section 22, item 22.1 — Police Record**" in item_text and
              "Disposition date** *(item location" not in item_text)

        s = base_session()
        s["events"][0]["reporting"]["reportable"] = "no"
        c, o = vs(s, "vs-no.json")
        check("reportable='no' is rejected — the tool never calls a matter unreportable",
              c == 1 and "unreportable" in o.lower(), o.strip()[-300:])

        s = base_session()
        s["privacy_tier"] = "secret"
        c, o = vs(s, "vs-tier.json")
        check("unknown privacy tier fails", c == 1)

        s = base_session()
        s["events"][0]["guidelines"] = ["G", "Z"]
        c, o = vs(s, "vs-guideline.json")
        check("invalid guideline letter fails", c == 1)

        s = base_session()
        s["narrative"] = "I was arrested on 3 March 2026."
        p = tmp / "vs-stamp.json"
        p.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VALSESS, str(p), "--stamp-narrative")
        check("narrative stamping succeeds", c == 0 and "stamped" in o.lower(),
              o.strip()[-300:])
        stamped = json.loads(p.read_text(encoding="utf-8"))
        stamped["narrative"] = "I was arrested on 3 March 2026, but it was minor."
        p.write_text(json.dumps(stamped), encoding="utf-8")
        c, o = run(VALSESS, str(p))
        check("altering the narrative after stamping fails",
              c == 1 and "altered" in o.lower(), o.strip()[-300:])

        s = base_session()
        s["stage_log"] = [{"stage": "intake"}, {"stage": "requirements"}]
        p = tmp / "vs-log.json"
        p.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VALSESS, str(p))
        check("stage log accepted and length recorded", c == 0)
        rec = json.loads(p.read_text(encoding="utf-8"))
        rec["stage_log"] = [{"stage": "intake"}]
        p.write_text(json.dumps(rec), encoding="utf-8")
        c, o = run(VALSESS, str(p))
        check("shrinking the stage log fails — append-only",
              c == 1 and "shrank" in o.lower(), o.strip()[-300:])

        s = base_session()
        s["events"][0]["reporting"]["reportable"] = "no"
        pbad = tmp / "vs-verify.json"
        pbad.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VERIFY, str(pkg), str(pbad))
        check("verify_output rejects a package whose session file is unsound",
              c == 1 and "session:" in o.lower(), o.strip()[-300:])

        print("\nDCSA Library — locator, tiering, retrieval, citation gate")
        MINI = ROOT / "tests" / "fixtures" / "mini-library"

        c, o = run(CHECKLIB, str(MINI))
        check("mini-library validates", c == 0, o.strip()[-300:])
        check("tier detected as ESSENTIALS", "ESSENTIALS" in o, o.strip()[-200:])
        check("case mismatch in the entry point is reported",
              "CASE MISMATCH" in o and "COLLECTIONS.json" in o, o.strip()[-300:])

        # PLATFORM-INDEPENDENT regression test for the check above.
        #
        # The case-mismatch warning exists to tell a maintainer that their
        # library's entry point names paths whose case does not match the disk —
        # fatal on macOS and Linux, invisible on Windows. An earlier find_ci
        # established exactness with Path.exists(), which on case-insensitive
        # NTFS answers True for the wrong case. So the check did nothing on the
        # one platform the maintainer builds on, and this suite passed on Linux
        # while the shipped behaviour was broken for the person relying on it.
        #
        # Asserting through the mini-library fixture alone could not catch that:
        # the fixture test passes on Linux either way. This one compares against
        # real directory entries, so it fails on ANY platform if find_ci starts
        # trusting the filesystem again.
        sys.path.insert(0, str(ROOT / "scripts"))
        import library_paths as _lp
        cdir = tmp / "case-probe"
        (cdir / "MixedCase").mkdir(parents=True)
        (cdir / "MixedCase" / "File.TXT").write_text("x", encoding="utf-8")
        _lp._listing_cache.clear()
        p_exact, ex = _lp.find_ci(cdir, "MixedCase/File.TXT")
        check("find_ci: exact case reports exact=True", p_exact is not None and ex is True)
        _lp._listing_cache.clear()
        p_wrong, ex = _lp.find_ci(cdir, "mixedcase/file.txt")
        check("find_ci: wrong case still resolves", p_wrong is not None,
              "the library's own entry point relies on this")
        check("find_ci: wrong case reports exact=False on EVERY platform",
              ex is False,
              "on NTFS a Path.exists() check would answer True and hide the mismatch")
        _lp._listing_cache.clear()
        p_missing, ex = _lp.find_ci(cdir, "MixedCase/nope.txt")
        check("find_ci: a genuinely absent path returns None", p_missing is None)

        # The entry point mixes real paths with prose that mentions one. The
        # real library's retrieval_config.json holds "Resolve aliases from
        # CATALOG/ALIASES.json." — reported as a missing file until this fix.
        # A trust-anchor script that cries wolf gets skimmed past.
        import check_library as _cl
        for good in ("ROBOT_READABLE_DIRECTORY/CATALOG/collections.json",
                     "MANIFESTS/documents.jsonl"):
            check(f"looks_like_path accepts {good!r}", _cl.looks_like_path(good))
        for bad, why in (
            ("Resolve aliases from CATALOG/ALIASES.json.", "prose mentioning a path"),
            ("https://example.invalid/a/b.json", "a URL"),
            ("collections.json", "no directory component"),
            ("", "empty"),
        ):
            check(f"looks_like_path rejects {why}", not _cl.looks_like_path(bad))
        check("absent search bundle is reported as optional, not an error",
              "optional 'Search' bundle" in o and c == 0)

        c, o = run(CHECKLIB, str(tmp))  # a real folder that isn't a library
        check("a non-library folder is refused", c == 1 and "DOES NOT LOOK LIKE" in o.upper(),
              o.strip()[-200:])

        c, picked, o = run_json(RETRIEVAL, "--library", str(MINI),
                                "--guidelines", "G,J", "--limit", "4")
        cases = picked.get("cases", [])
        check("retrieval returns cases for G,J", len(cases) == 4, o.strip()[-200:])
        check("retrieval returns BOTH outcomes, never one-sided",
              len({x["outcome"] for x in cases}) > 1,
              f"outcomes: {[x['outcome'] for x in cases]}")
        check("pre-SEAD-4 decisions excluded by default",
              all(x["group"] == "POST_SEAD_4" for x in cases),
              f"groups: {[x['group'] for x in cases]}")
        check("unparseable/unreadable stems are dropped, not guessed at",
              picked.get("library_case_count") == 7)
        check("retrieval output carries the no-prediction reminder",
              "selection-biased" in o)

        c, data, o = run_json(RETRIEVAL, "--library", str(MINI), "--guidelines",
                              "G,J", "--limit", "6", "--include-pre-sead4")
        groups = {x["group"] for x in data.get("cases", [])}
        check("pre-SEAD-4 included only when explicitly asked", "PRE_SEAD_4" in groups)

        c, o = run(RETRIEVAL, "--library", str(MINI), "--verify-case", "90-00001")
        check("a case in the library verifies", c == 0 and '"in_library": true' in o)
        c, o = run(RETRIEVAL, "--library", str(MINI), "--verify-case", "24-99999")
        check("a case NOT in the library is rejected", c == 1 and '"in_library": false' in o)

        print("\ndirective quotations must match the section they cite")
        # The split guarantees an unrelated guideline never enters the context
        # window. It does not guarantee that what gets quoted is what the file
        # says. An unverifiable quotation is treated exactly like an
        # unverifiable case citation: as fabricated.
        MINI4 = (MINI / "ROBOT_READABLE_DIRECTORY" / "TEXT" / "PERSONNEL_VETTING"
                 / "SECURITY_EXECUTIVE_AGENT_DIRECTIVES_(SEAD)"
                 / "SEAD-4_Adjudicative-Guidelines")
        real = (MINI4 / "09_Guideline_G_Alcohol_Consumption.md").read_text(
            encoding="utf-8").strip().splitlines()[-1]

        def quoted(passage: str, attrib: str):
            def m(t):
                return t.replace("## Narrative",
                                 f"> {passage}\n> — {attrib}\n\n## Narrative", 1)
            return m

        MARK = "## Incident 1 of 1"

        def with_quote(passage: str, attrib: str) -> str:
            return pkg.read_text(encoding="utf-8").replace(
                MARK, f"> {passage}\n> — {attrib}\n\n{MARK}", 1)

        c, o = run(VERIFY, str(pkg), str(sp), "--library", str(MINI))
        check("baseline package still passes with the quote gate active", c == 0,
              o.strip()[-200:])

        pq = tmp / "quote-good.md"
        pq.write_text(with_quote(real, "SEAD 4, Guideline G"), encoding="utf-8")
        c, o = run(VERIFY, str(pq), str(sp), "--library", str(MINI))
        check("a faithful quote from the cited section passes", c == 0,
              o.strip()[-260:])

        pq2 = tmp / "quote-wrong-section.md"
        pq2.write_text(with_quote(real, "SEAD 4, Guideline L"), encoding="utf-8")
        c, o = run(VERIFY, str(pq2), str(sp), "--library", str(MINI))
        check("the same text attributed to the WRONG guideline fails",
              c == 1 and "does not appear in that section" in o, o.strip()[-260:])

        pq3 = tmp / "quote-invented.md"
        pq3.write_text(with_quote(
            "The directive requires abstinence for a period of five years "
            "before eligibility may be restored.", "SEAD 4, Guideline G"),
            encoding="utf-8")
        c, o = run(VERIFY, str(pq3), str(sp), "--library", str(MINI))
        check("an invented passage attributed to a real guideline fails",
              c == 1 and "does not appear in that section" in o, o.strip()[-260:])

        # Isolate library discovery from the machine running the suite: a dev
        # box with a real DCSA Library installed at ~/Documents/DCSA Library
        # (a conventional location library_paths.py deliberately searches)
        # would otherwise find it and this test would silently stop testing
        # the "no library" path it's named for. Point HOME/USERPROFILE at an
        # empty temp dir instead of unsetting the feature under test.
        no_lib_home = tmp / "no-library-home"
        no_lib_home.mkdir(exist_ok=True)
        c, o = run(VERIFY, str(pq), str(sp), env={
            "HOME": str(no_lib_home), "USERPROFILE": str(no_lib_home),
            "AIA_LIBRARY": ""})   # no --library
        check("a directive quote with no library available fails",
              c == 1 and "treated as fabricated" in o, o.strip()[-260:])

        print("\nsection-level directive text — only what the matter needs")
        # Loading a whole directive to answer a question about one guideline
        # puts twelve other guidelines in front of the model. That is the
        # condition under which text gets attributed to the wrong guideline.
        # These tests assert the narrowing is real, and that a missing section
        # NEVER silently degrades into reading the full directive.
        SEADLOOK = ROOT / "scripts" / "sead_lookup.py"
        c, sel, o = run_json(SEADLOOK, "--library", str(MINI),
                             "--guidelines", "G,J", "--json")
        picked = [Path(x).name for x in sel.get("read_only_these", [])]
        check("lookup resolves the requested guidelines", c == 0 and sel.get("ok"),
              o.strip()[-200:])
        check("it returns exactly the guidelines asked for, plus the common file",
              sorted(picked) == sorted([
                  "02_Appendix_A_Introduction_and_Adjudicative_Process.md",
                  "09_Guideline_G_Alcohol_Consumption.md",
                  "12_Guideline_J_Criminal_Conduct.md"]), f"got {picked}")
        check("no unrelated guideline is loaded",
              not any(f"Guideline_{g}_" in n for n in picked
                      for g in "ABCDEFHIKLM" if g not in ("G", "J")),
              f"leaked: {picked}")
        check("the whole-person appendix always travels with a guideline",
              any("Appendix_A_Introduction" in n for n in picked),
              "a guideline quoted without it is a fragment presented as a rule")

        # SEAD-3's additive sections are alternatives, not a ladder: Section G
        # and Section H each apply *in addition to Section F*, so a Top Secret
        # holder reads F + H, NOT F + G + H.
        c, ts, o = run_json(SEADLOOK, "--library", str(MINI), "--reporting",
                            "--access", "ts_q", "--json")
        names = [Path(x).name for x in ts.get("read_only_these", [])]
        check("TS/Q gets the Top Secret section", c == 0
              and any(n.startswith("04_Top_Secret") for n in names), f"{names}")
        check("TS/Q does NOT also get the Secret section",
              not any(n.startswith("03_Secret") for n in names),
              "Section H applies in addition to F, not in addition to G")
        check("every access tier still gets Section F",
              any(n.startswith("02_All_Covered") for n in names), f"{names}")
        c, base, _ = run_json(SEADLOOK, "--library", str(MINI), "--reporting",
                              "--access", "baseline", "--json")
        bn = [Path(x).name for x in base.get("read_only_these", [])]
        check("baseline gets the Secret section and not the TS one",
              any(n.startswith("03_Secret") for n in bn)
              and not any(n.startswith("04_Top_Secret") for n in bn), f"{bn}")

        # The failure mode that matters: a missing section must stop the quote,
        # not fall back to the full directive.
        import shutil as _sh
        broken = tmp / "lib-no-split"
        _sh.copytree(MINI, broken)
        _sh.rmtree(broken / "ROBOT_READABLE_DIRECTORY" / "TEXT")
        c, o = run(SEADLOOK, "--library", str(broken), "--guidelines", "G")
        check("a missing split exits non-zero", c == 1, o.strip()[-160:])
        check("and says not to read the whole directive instead",
              "do not read the whole directive" in o.lower(), o.strip()[-200:])
        c, o = run(SEADLOOK, "--library", str(MINI), "--guidelines", "Z")
        check("an invalid guideline letter is refused", c == 1, o.strip()[-160:])

        # ISL 2021-02 is the reporting axis's source of record, and it lives
        # under INDUSTRIAL_SECURITY rather than PERSONNEL_VETTING. It went
        # unexercised long enough for a lookup against it to raise
        # AttributeError in the quote gate, so it is tested the same way the
        # directives are.
        c, isl, o = run_json(SEADLOOK, "--library", str(MINI), "--isl",
                             "--isl-tables", "4", "--json")
        iname = [Path(x).name for x in isl.get("read_only_these", [])]
        check("the ISL split is reachable from the lookup",
              c == 0 and isl.get("ok"), o.strip()[-220:])
        check("asking for one ISL table returns that table and the overview",
              sorted(iname) == sorted([
                  "01_Overview_and_Adverse_Information_Guidance.md",
                  "05_Table_4_Foreign_Travel.md"]), f"got {iname}")
        check("no unrelated ISL table is loaded",
              not any(f"Table_{t}_" in n for n in iname for t in "123"),
              f"leaked: {iname}")

        # The advisor knows which CORPUS table matched before it knows which
        # ISL table backs it, so it can select by the thing it already holds.
        c, byv, o = run_json(SEADLOOK, "--library", str(MINI), "--isl",
                             "--verifies", "corpus/reporting/tables/top-secret-q.yaml",
                             "--json")
        vn = [Path(x).name for x in byv.get("read_only_these", [])]
        check("a corpus table resolves to the ISL section that verifies it",
              c == 0 and any(n.startswith("04_Table_3") for n in vn), f"{vn}")
        c, o = run(SEADLOOK, "--library", str(MINI), "--isl",
                   "--verifies", "corpus/reporting/tables/invented.yaml")
        check("a corpus table nothing verifies is refused, not guessed at",
              c == 1 and "source of record" in o, o.strip()[-200:])

        # The regression that made this necessary: an unknown directive name
        # used to fall through to the SEAD-4 manifest, so a caller asking for
        # the ISL got the guidelines and no error.
        sys.path.insert(0, str(ROOT / "scripts"))
        import library_paths as _lp
        check("an unknown directive name resolves to nothing, not to SEAD-4",
              _lp.sead_manifest(MINI, "NOT-A-DIRECTIVE") is None,
              "it used to fall through to the guidelines manifest")
        check("the ISL resolves to its own folder under INDUSTRIAL_SECURITY",
              "INDUSTRIAL_SECURITY" in _lp.SPLIT_FOLDERS["ISL-2021-02"])

        c, o = run(SEADLOOK, "--library", str(broken), "--isl")
        check("a missing ISL split exits non-zero", c == 1, o.strip()[-160:])
        check("and says not to read the whole letter instead",
              "do not read the whole letter" in o.lower(), o.strip()[-200:])

        isl_body = ("FIXTURE ISL table 4: foreign travel reporting only.")
        pi = tmp / "quote-isl.md"
        pi.write_text(with_quote(isl_body, "ISL 2021-02, Table 4"),
                      encoding="utf-8")
        c, o = run(VERIFY, str(pi), str(sp), "--library", str(MINI))
        check("a real ISL table passage passes the quote gate", c == 0,
              o.strip()[-300:])
        pi2 = tmp / "quote-isl-bad.md"
        pi2.write_text(with_quote(
            "Covered individuals must report all foreign travel ninety days in "
            "advance without exception.", "ISL 2021-02, Table 4"),
            encoding="utf-8")
        c, o = run(VERIFY, str(pi2), str(sp), "--library", str(MINI))
        check("an invented ISL passage fails against the table file",
              c == 1 and "does not appear in that section" in o,
              o.strip()[-260:])
        # A part that does not exist must not be a way past the gate.
        pi3 = tmp / "quote-isl-nopart.md"
        pi3.write_text(with_quote(
            "Covered individuals must report all foreign travel ninety days in "
            "advance without exception.", "ISL 2021-02, Table 9"),
            encoding="utf-8")
        c, o = run(VERIFY, str(pi3), str(sp), "--library", str(MINI))
        check("a quote attributed to a section that does not exist fails",
              c == 1 and "not a part of that document" in o, o.strip()[-260:])

        c, o = run(CHECKLIB, str(MINI))
        check("check_library reports section-level availability",
              "Directive text (section level)" in o and "ABCDEFGHIJKLM" in o,
              o.strip()[-200:])
        check("check_library reports the ISL split too",
              "ISL 2021-02" in o and "tables 1,2,3,4" in o, o.strip()[-300:])

        print("\nthe prompts tell agents to narrow, not to browse")
        agents_md = flatten((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        check("AGENTS.md carries the narrow-loading rule",
              "sead_lookup.py" in agents_md
              and "never read a whole directive" in agents_md.lower())
        for rel in ("agents/core/classifier.md", "agents/core/requirements-advisor.md",
                    "agents/conductor.md"):
            body = flatten((ROOT / rel).read_text(encoding="utf-8"))
            check(f"{rel.split('/')[-1]} routes through the lookup",
                  "sead_lookup.py" in body)
        check("AGENTS.md names the ISL lookup, not just the two directives",
              "--isl" in agents_md,
              "the reporting axis's source of record was reachable by script "
              "but not mentioned in the rule that tells agents to use it")
        ra = flatten((ROOT / "agents" / "core" / "requirements-advisor.md")
                     .read_text(encoding="utf-8"))
        check("requirements-advisor can select an ISL table by the corpus "
              "table it already matched", "--verifies" in ra)
        check("requirements-advisor knows G and H are alternatives, not a ladder",
              "not f + g + h" in ra.lower() or "alternatives, not a ladder" in ra.lower())

        print("\nsplit_sead_text.py — the splitter proves its own output")
        SPLIT = ROOT / "scripts" / "split_sead_text.py"
        check("scripts/split_sead_text.py exists", SPLIT.exists())
        if SPLIT.exists():
            src = SPLIT.read_text(encoding="utf-8")
            check("it refuses to write when reassembly fails",
                  "REASSEMBLY FAILED" in src and "Nothing was written" in src)
            check("it requires each anchor to match exactly once",
                  "expected exactly 1" in src)
            check("it checks every section starts at its own heading",
                  "does not start at its heading" in src)
            check("it preserves OCR artifacts rather than correcting them",
                  "faithful" in src.lower() and "correct" in src.lower())
            c, o = run(SPLIT, "--help")
            check("--help works", c == 0, o.strip()[-160:])

        print("\nverify_output.py — citations checked against the library")
        lib_pkg = tmp / "libcite.md"
        base = pkg.read_text(encoding="utf-8")
        lib_pkg.write_text(base + "\n\nSee ISCR Case No. 90-00001.\n", encoding="utf-8")
        c, o = run(VERIFY, str(lib_pkg), str(sp), "--library", str(MINI))
        check("a real library case passes the citation gate", c == 0, o.strip()[-300:])

        lib_bad = tmp / "libcite-bad.md"
        lib_bad.write_text(base + "\n\nSee ISCR Case No. 24-99999.\n", encoding="utf-8")
        c, o = run(VERIFY, str(lib_bad), str(sp), "--library", str(MINI))
        check("a fabricated case fails against the library",
              c == 1 and "fabricated" in o.lower(), o.strip()[-300:])

        print("\ntier-high package with NO knowledgeable parties")
        # Regression: the privacy boilerplate must not itself look like a
        # Person N reference, or a user whose matter nobody else knows about
        # gets a package that cannot pass verification.
        s = base_session()
        s["events"][0]["persons"] = []
        s["events"][0]["narrative"] = "I was arrested on 3 March 2026 for OWI."
        s.pop("entities", None)
        pkg_np, sp_np = build(s, tmp)
        c, o = run(VERIFY, str(pkg_np), str(sp_np))
        check("package with no other people still verifies", c == 0, o.strip()[-300:])

        print("\ncourt_lookup.py — recognition aid, never a determination")
        courts = yaml.safe_load(
            (ROOT / "corpus" / "courts" / "state-courts.yaml").read_text(encoding="utf-8"))
        st = courts["states"]
        check("all 50 states plus DC are present", len(st) == 51, f"got {len(st)}")
        check("every jurisdiction ships unverified",
              all(not s.get("verified") for s in st.values()),
              str([k for k, s in st.items() if s.get("verified")]))
        check("Louisiana uses parishes, Alaska uses judicial districts",
              st["LA"]["unit_label"] == "Parish"
              and st["AK"]["organized_by"] == "judicial_district")

        c, d, o = run_json(COURTS, "--state", "IA", "--county", "Black Hawk",
                           "--offense", "owi")
        check("Iowa nudge names the right court and county",
              "Iowa District Court" in d.get("nudge", "")
              and "Black Hawk" in d.get("nudge", ""), o.strip()[-200:])
        check("unverified entries are labelled as guesses",
              d.get("confidence") == "unverified_guess")
        check("the nudge is framed as a question to confirm, not a value",
              d.get("ask_first", "").startswith("What court")
              and "never this suggestion" in d.get("usage_rule", ""))
        check("a fallback exists for users who still don't know",
              "clerk" in d.get("fallback_if_still_unknown", "").lower())

        c, d, o = run_json(COURTS, "--state", "NJ", "--offense", "dui")
        check("New Jersey DWI points at Municipal Court, not Superior",
              "Municipal Court" in d["nudge"] and "Superior" not in d["nudge"].split("IMPORTANT")[0],
              d["nudge"][:160])
        check("no court is offered twice in one nudge",
              d["nudge"].count("Municipal Court for") <= 1
              and "also have been a Municipal Court" not in d["nudge"])

        c, d, o = run_json(COURTS, "--state", "WI", "--offense", "owi")
        check("Wisconsin flags first-offense OWI as a forfeiture",
              "forfeiture" in d["nudge"].lower())

        c, d, o = run_json(COURTS, "--state", "PA")
        check("Pennsylvania warns Clerk of Courts vs Prothonotary",
              "Prothonotary" in (d.get("notes") or "")
              and "Clerk of Courts" in d["records_custodian"])

        c, d, o = run_json(COURTS, "--state", "ZZ")
        check("an unknown state falls back rather than inventing a court",
              c == 1 and "fallback" in o.lower())

        c, o = run(COURTS, "--check-links")
        check("link checker lists URLs and makes no network calls",
              c == 0 and "no network calls" in o, o.strip()[-200:])

        print("\nshipped corpus must stay a skeleton")
        # The repo publishes the STRUCTURE; the populated corpus is distributed
        # separately and lives outside the repo. It is easy to populate the
        # repo's own corpus/ in place while building, and then publish
        # government text you meant to distribute another way. This check fails
        # the suite before that reaches a push.
        # Parse the actual values rather than string-matching: these flags are
        # discussed in comments and documentation all over the corpus, and a
        # naive match flags BUILDING.md for explaining the rule.
        populated = []
        for p in sorted((ROOT / "corpus").rglob("*")):
            if not p.is_file() or p.name.startswith("_"):
                continue
            if p.suffix in (".yaml", ".yml"):
                try:
                    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                except Exception:  # noqa: BLE001 — validate_corpus reports these
                    continue
            elif p.suffix == ".md":
                text = p.read_text(encoding="utf-8", errors="replace")
                if not text.startswith("---"):
                    continue  # prose, not a corpus file with frontmatter
                try:
                    data = yaml.safe_load(text.split("---", 2)[1]) or {}
                except Exception:  # noqa: BLE001
                    continue
            else:
                continue
            if not isinstance(data, dict):
                continue
            for flag in ("maintainer_verified", "verbatim"):
                if data.get(flag) is True:
                    populated.append(f"{p.relative_to(ROOT)} ({flag})")
        cases = [c for c in (ROOT / "corpus" / "doha" / "cases").glob("*.md")
                 if not c.name.startswith("_")]
        check("no verified/verbatim corpus files in the repo skeleton",
              not populated,
              "these belong in the separately distributed corpus, not the "
              f"repo: {populated}")
        check("no DOHA case files in the repo skeleton", not cases,
              f"{len(cases)} case file(s) present; cases are distributed "
              "separately")

        print("\ngranular questions — one fact per ask, ladders for depth")
        VALID_TRIGGERS = {"always", "vague", "answered_yes", "answered_no",
                          "pending", "quantitative_tension"}
        for g in "GJFHE":
            d = yaml.safe_load((ROOT / "corpus" / "checklists" /
                                f"guideline-{g}.yaml").read_text(encoding="utf-8"))
            els = d["elements"]
            fups = [f for e in els for f in e.get("followups", [])]
            check(f"guideline {g} uses conditional ladders", len(fups) > 0,
                  f"{len(els)} elements, no followups")
            bad = [f.get("trigger") for f in fups if f.get("trigger") not in VALID_TRIGGERS]
            check(f"guideline {g} triggers are all recognised", not bad, str(bad))
            # A followup with no ask is a silently-lost question.
            check(f"guideline {g} followups all carry a question",
                  all(str(f.get("ask", "")).strip() for f in fups))

        gcl = yaml.safe_load((ROOT / "corpus" / "checklists" /
                              "guideline-G.yaml").read_text(encoding="utf-8"))
        gids = {e["id"] for e in gcl["elements"]}
        for needed in ("incident-location", "court-identity", "case-number",
                       "charge-language", "charge-level", "licence-action",
                       "consumption-account", "disposition-outcome"):
            check(f"guideline G asks for {needed}", needed in gids)
        # The old bundled question must be gone.
        asks = " ".join(e["ask"] for e in gcl["elements"])
        check("guideline G no longer bundles location+circumstances+BAC",
              "location type, circumstances" not in asks)
        check("guideline G asks the BAC reading separately from the test",
              any("reading" in f.get("ask", "").lower()
                  for e in gcl["elements"] for f in e.get("followups", [])))

        print("\nplausibility — flag the tension, never state a figure")
        pl = yaml.safe_load((ROOT / "corpus" / "checks" /
                             "plausibility.yaml").read_text(encoding="utf-8"))
        cids = {c["id"] for c in pl["checks"]}
        check("the drinks-vs-test-result check exists",
              "drinks-vs-test-result" in cids)
        drinks = next(c for c in pl["checks"] if c["id"] == "drinks-vs-test-result")
        check("it forbids asserting a computed BAC",
              any("bac would have been" in str(s).lower()
                  or "blood alcohol figure" in str(s).lower()
                  for s in drinks.get("never_say", [])))
        check("it forbids calling the account impossible",
              any("not possible" in str(s).lower() for s in drinks.get("never_say", [])))
        check("its wording frames the risk as how a reader will read it",
              "understating" in drinks["say"].lower())
        check("a category ABV reference exists without brand claims",
              "typical_abv_by_category" in pl and "bud" not in
              json.dumps(pl).lower())
        check("it is raised at most once per matter",
              "once per matter" in pl.get("user_facing_rule", "").lower())

        ic = flatten((ROOT / "agents" / "core" / "interviewer.md").read_text(encoding="utf-8"))
        check("interviewer forbids bundled questions",
              "Never bundle" in ic and "One fact per question" in ic)
        check("interviewer forbids stating a BAC",
              "Never compute or state a blood alcohol figure" in ic)
        cc = flatten((ROOT / "agents" / "optional" /
                      "consistency-checker.md").read_text(encoding="utf-8"))
        check("consistency checker forbids stating a BAC",
              "Never compute or state a blood alcohol figure" in cc)
        check("quantitative findings are never treated as hard contradictions",
              "quantitative` findings are never `hard" in cc)

        print("\nprose, not menus")
        for f, label in ((ROOT / "agents" / "conductor.md", "conductor"),
                         (ROOT / "agents" / "core" / "interviewer.md", "interviewer"),
                         (ROOT / "AGENTS.md", "AGENTS.md")):
            body = flatten(f.read_text(encoding="utf-8"))
            check(f"{label} forbids rendering menus",
                  "never render a menu" in body.lower()
                  or "Never build a menu" in body
                  or "never menus" in body.lower())

        print("\nrevised interview flow — complete, factual, and internally reviewed")
        conductor_flat = flatten((ROOT / "agents" / "conductor.md").read_text(encoding="utf-8"))
        intake_flat = flatten((ROOT / "agents" / "core" / "intake.md").read_text(encoding="utf-8"))
        triage_flat = flatten((ROOT / "agents" / "core" / "triage.md").read_text(encoding="utf-8"))
        thread_flat = flatten((ROOT / "agents" / "core" / "thread-detector.md").read_text(encoding="utf-8"))
        candor_flat = flatten((ROOT / "agents" / "optional" / "candor-reviewer.md").read_text(encoding="utf-8"))
        check("intake asks what happened and then goes to triage",
              "What happened?" in intake_flat and "triage runs immediately" in intake_flat)
        check("intake carries the separate-proceeding limitation",
              "cannot determine how a security report may interact" in intake_flat
              and "discoverability" in intake_flat)
        check("triage does not claim the report joins another record",
              "what they file becomes a record" not in triage_flat.lower()
              and "counsel will want to know" not in triage_flat.lower())
        check("workflow has no essentials-versus-thorough offer",
              "Two ways to do this" not in conductor_flat
              and "Honor the session's pace choice" not in ic)
        check("routine answers use factual rather than therapeutic framing",
              "Thank you" in ic and "does not turn the interview into counseling" in ic)
        check("treatment question does not assume what has happened",
              "that hasn't come up yet" in ic
              and "Never preface the question" in ic)
        check("candor pass is invisible and becomes a neutral follow-up",
              "Invisible review" in candor_flat
              and "neutral factual follow-up" in candor_flat
              and "findings go to the user" not in candor_flat.lower())
        check("independent incidents queue without a report-choice question",
              "finish this incident first" in thread_flat
              and "Do not ask whether they want to report it" in thread_flat)
        check("same causal chain remains one incident narrative",
              "share the same event, people, timeframe, or causal chain" in thread_flat)
        developer = flatten((ROOT / "agents" / "core" /
                             "incident-developer.md").read_text(encoding="utf-8"))
        chronology = yaml.safe_load((ROOT / "corpus" / "checklists" /
                                     "_INCIDENT_CHRONOLOGY.yaml").read_text(encoding="utf-8"))
        profiles = yaml.safe_load((ROOT / "corpus" / "checklists" /
                                   "_INCIDENT_PROFILES.yaml").read_text(encoding="utf-8"))
        required_phases = set(chronology.get("required_phases", []))
        check("incident developer reconstructs every incident before narrative drafting",
              "Reconstruct the incident in time order:" in developer
              and "immediate aftermath" in developer
              and "future developments" in developer)
        check("chronology model requires before, during, after, current, and future facts",
              required_phases == {
                  "before", "precipitating_circumstances", "decisions_and_actions",
                  "incident", "immediate_aftermath", "later_consequences",
                  "current_status", "future_developments",
              })
        profile_ids = {p.get("id") for p in profiles.get("profiles", [])}
        check("specialized incident profiles cover the major reporting families",
              {"impaired-driving", "violent-conduct",
               "domestic-or-intimate-partner-violence",
               "arrest-or-criminal-process", "foreign-contact-or-influence",
               "financial-event", "substance-use-or-treatment",
               "information-or-technology"} <= profile_ids)
        check("multiple profiles do not split one causal chain",
              "Several profiles may apply to one incident" in developer)
        alcohol_elements = {
            element.get("id"): element
            for element in gcl.get("elements", [])
        }
        check("alcohol checklist requires the pre-incident decision chain",
              all(element_id in alcohol_elements for element_id in (
                  "pre-incident-activity", "drinking-circumstances",
                  "decision-to-drive", "behavior-typicality")))
        check("decision-chain questions remain one fact at a time",
              all(" and " not in alcohol_elements[element_id]["ask"].lower()
                  for element_id in (
                      "pre-incident-activity", "drinking-circumstances",
                      "decision-to-drive", "behavior-typicality")))
        narrative_writer_flat = flatten((ROOT / "agents" / "core" /
                                         "narrative-writer.md").read_text(encoding="utf-8"))
        check("OWI narrative begins before the traffic stop",
              "begin before the stop" in narrative_writer_flat
              and "whether that behavior was typical" in narrative_writer_flat)
        check("all conclusions wait for the final combined analysis",
              "All conclusions wait" in conductor_flat
              and "Final combined reporting analysis" in conductor_flat)

        print("\nrecords: where they live, not whether they exist")
        da = flatten((ROOT / "agents" / "optional" /
                      "documents-advisor.md").read_text(encoding="utf-8"))
        check("documents advisor stops asking whether documentation exists",
              "Never ask whether documentation exists" in da)
        check("arrest and jail facts automatically imply routine records",
              "automatically add the arrest/booking record and developing court record" in da)
        check("it explains that a security officer must go and fetch them",
              "where to look" in da.lower())
        check("checklists name record locations rather than asking if records exist",
              any("record" in e for e in
                  [json.dumps(x) for x in gcl["elements"]]))

        print("\nform standard — SF-86 until the PVQ fully launches")
        cp = yaml.safe_load((ROOT / "corpus" / "forms" /
                             "collection-policy.yaml").read_text(encoding="utf-8"))
        check("collection standard is sf86", cp.get("collection_standard") == "sf86")
        check("the switch is documented as one line",
              "one line" in cp.get("standard_switch_note", "").lower()
              or "one value" in cp.get("standard_switch_note", "").lower())
        diffs = cp.get("material_differences", {})
        check("7-vs-5-year lookback difference recorded",
              "7" in str(diffs.get("criminal_lookback", {}).get("sf86", ""))
              and "5" in str(diffs.get("criminal_lookback", {}).get("pvq", "")))
        check("$300-vs-$1,000 traffic threshold recorded",
              "300" in str(diffs.get("traffic_fine_threshold", {}).get("sf86", ""))
              and "1,000" in str(diffs.get("traffic_fine_threshold", {}).get("pvq", "")))
        check("superset rule collects depth but never borrows scope",
              cp.get("collect_superset") is True
              and "threshold" in cp.get("collect_superset_rule", "").lower())
        intake_flat = flatten((ROOT / "agents" / "core" / "intake.md").read_text(encoding="utf-8"))
        check("intake says SF-86 is the current standard",
              "SF-86" in intake_flat and "not fully launched" in intake_flat)
        iv_flat = flatten((ROOT / "agents" / "core" / "interviewer.md").read_text(encoding="utf-8"))
        check("interviewer knows the two forms differ in scope",
              "7 years" in iv_flat and "$1,000" in iv_flat)

        print("\nentity capture — every organisation named AND located")
        ec = yaml.safe_load((ROOT / "corpus" / "forms" /
                             "entity-capture.yaml").read_text(encoding="utf-8"))
        eids = {e["id"] for e in ec["entities"]}
        for needed in ("offense-location", "citing-agency",
                       "arresting-agency-if-different", "court", "venue"):
            check(f"entity-capture defines {needed}", needed in eids)
        arr = next(e for e in ec["entities"] if e["id"] == "arresting-agency-if-different")
        check("the citing/booking agency split is explained",
              "sheriff" in arr["note"].lower() and "booking" in arr["note"].lower())
        check("address collection is the union of both forms",
              set(ec["collect"]) >= {"street", "city", "county", "state", "zip"})
        for g in ("G", "J"):
            d = yaml.safe_load((ROOT / "corpus" / "checklists" /
                                f"guideline-{g}.yaml").read_text(encoding="utf-8"))
            ids = {e["id"] for e in d["elements"]}
            check(f"guideline {g} asks whether the arresting agency differed",
                  "arresting-agency-if-different" in ids)
            court = next(e for e in d["elements"] if e["id"] == "court-identity")
            check(f"guideline {g} follows the court name with its address",
                  any("address" in f.get("ask", "").lower()
                      for f in court.get("followups", [])))
        gG = yaml.safe_load((ROOT / "corpus" / "checklists" /
                             "guideline-G.yaml").read_text(encoding="utf-8"))
        check("guideline G asks for the venue by name",
              "venue" in {e["id"] for e in gG["elements"]})
        er_flat = flatten((ROOT / "agents" / "optional" /
                           "entity-resolver.md").read_text(encoding="utf-8"))
        # The business/person call must come from asking, not from reading the
        # name. The old rule — "practice named after a person = natural person"
        # — broke on this corpus's own worked example: Casey's Bar is a person's
        # name, so the resolver would have refused to look up the venue every
        # entity-capture example is built around.
        er = flatten((ROOT / "agents" / "optional" / "entity-resolver.md")
                     .read_text(encoding="utf-8"))
        iv = flatten((ROOT / "agents" / "core" / "interviewer.md")
                     .read_text(encoding="utf-8"))
        tiers_raw = (ROOT / "corpus" / "privacy-tiers.yaml").read_text(encoding="utf-8")
        tiers = yaml.safe_load(tiers_raw)
        check("business-vs-person is decided by asking, not by parsing the name",
              tiers.get("business_determination", {}).get("method") == "ask_the_user"
              and tiers["business_determination"].get("never") == "infer_from_name")
        check("the old name-parsing rule is gone from the corpus",
              "when the name of the practice is the person's name" not in tiers_raw)
        for doc, name in ((er, "entity-resolver"), (iv, "interviewer")):
            check(f"{name} says not to infer a person from the name",
                  "never" in doc.lower() and "casey's bar" in doc.lower(),
                  "the worked example must appear as the counter-example")
        # Business does not imply a publishable address.
        hb = tiers.get("home_based_business", {})
        check("a home-based business keeps its name", hb.get("on_home_based", {}).get("use_name") is True)
        check("a home-based business does NOT get its address collected",
              hb.get("on_home_based", {}).get("collect_address") is False)
        check("a home-based business is never looked up",
              hb.get("on_home_based", {}).get("perform_lookup") is False)
        check("the home-based question is scoped, not asked of every entity",
              "court" in hb.get("ask_when", "").lower()
              and "hospital" in hb.get("ask_when", "").lower(),
              "must exclude courts, police, hospitals, chains, bars")
        check("entity-resolver emits home_based in its record", "home_based" in er)

        # The network carve-out: search yes, fetch no.
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        deny = settings["permissions"]["deny"]
        check("WebFetch stays denied", "WebFetch" in deny)
        check("curl stays denied", "Bash(curl:*)" in deny)
        check("wget stays denied", "Bash(wget:*)" in deny)
        check("WebSearch is allowed for the entity lookup", "WebSearch" not in deny,
              "the resolver cannot do its job otherwise")
        check("the settings file explains why the line sits there",
              "entity-resolver" in json.dumps(settings)
              and "WebFetch" in settings.get("_network_comment", ""))
        agents_md = flatten((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        check("AGENTS.md states the carve-out and its exact shape",
              "entity-resolver" in agents_md and "web search" in agents_md.lower())
        check("AGENTS.md keeps reference material out of scope for both routes",
              "reference material" in agents_md.lower())
        check("entity-resolver is told search-only, never fetch",
              "never fetch a page" in er.lower() or "search only" in er.lower())

        check("entity resolver batches consent instead of four prompts",
              "Batch the consent" in er_flat)
        check("entity resolver knows records go to whichever agency created them",
              "created" in er_flat and "booking record" in er_flat)

        print("\nprior disclosure — don't make people re-litigate their own file")

        def with_pd(pd: dict, reporting: dict) -> dict:
            s = base_session()
            s["events"][0]["prior_disclosure"] = pd
            s["events"][0]["reporting"] = reporting
            return s

        ok_pd = {"status": "disclosed_unchanged",
                 "user_statement": "I put it on my 2020 SF-86",
                 "form_referenced": "sf86"}
        c, o = vs(with_pd(ok_pd, {"reportable": "consult_fso",
                                  "no_new_obligation_identified": True}), "pd-ok.json")
        check("a stated, unchanged prior disclosure is accepted", c == 0, o.strip()[-250:])

        c, o = vs(with_pd(ok_pd, {"reportable": "yes"}), "pd-yes.json")
        check("previously disclosed + 'yes' is rejected — that is rehashing",
              c == 1 and "already has" in o, o.strip()[-250:])

        c, o = vs(with_pd(ok_pd, {"reportable": "consult_fso"}), "pd-norelief.json")
        check("the relief must be recorded, not just spoken",
              c == 1 and "no_new_obligation_identified" in o, o.strip()[-250:])

        c, o = vs(with_pd({"status": "disclosed_unchanged"},
                          {"reportable": "consult_fso",
                           "no_new_obligation_identified": True}), "pd-nostmt.json")
        check("'disclosed_unchanged' requires the user's own words",
              c == 1 and "user_statement" in o, o.strip()[-250:])

        c, o = vs(with_pd({"status": "disclosed_but_changed", "user_statement": "x"},
                          {"reportable": "yes"}), "pd-changed.json")
        check("'disclosed_but_changed' requires what actually changed",
              c == 1 and "what_changed" in o, o.strip()[-250:])

        c, o = vs(with_pd({"status": "not_disclosed", "user_statement": "never came up"},
                          {"reportable": "yes",
                           "no_new_obligation_identified": True}), "pd-notdisc.json")
        check("relief cannot be claimed on an undisclosed matter",
              c == 1 and "only\navailable" in o.replace(" \n", "\n") or "only" in o,
              o.strip()[-250:])

        # Rendering: a previously-disclosed matter reads as context, and the
        # package must not instruct a fresh report for it.
        s = with_pd(ok_pd, {"reportable": "consult_fso",
                            "no_new_obligation_identified": True})
        pkg_pd, sp_pd = build(s, tmp)
        txt = pkg_pd.read_text(encoding="utf-8")
        check("package marks it previously disclosed, as context",
              "Previously disclosed" in txt and "context only" in txt)
        check("package records no new obligation and still says confirm",
              "No new reporting obligation identified" in txt
              and "security office" in txt)
        c, o = run(VERIFY, str(pkg_pd), str(sp_pd))
        check("a previously-disclosed package still verifies", c == 0, o.strip()[-250:])

        td = (ROOT / "agents" / "core" / "thread-detector.md").read_text(encoding="utf-8")
        squash = flatten(td)
        check("thread detector asks about prior disclosure before expanding",
              "disclosed on a previous SF-86 or PVQ" in squash
              and "BEFORE expanding" in td)
        check("thread detector warns that age is not mitigation for a false answer",
              "Age is not mitigation for an answer that was wrong" in squash)

        print("\nno legal deferral — the user already decided to disclose")
        tri = (ROOT / "agents" / "core" / "triage.md").read_text(encoding="utf-8")
        tri_flat = flatten(tri)
        check("triage forbids asking whether they want an attorney",
              "Never ask whether they want to consult an attorney" in tri_flat)
        check("triage forbids offering to pause for legal advice",
              "Never offer to stop, hold, or defer" in tri_flat)
        check("triage forbids attorney as a menu option",
              "Never put legal consultation in a numbered list of options" in tri_flat)
        check("uncharged-conduct trigger no longer routes to an attorney",
              "uncharged criminal conduct" in tri_flat.lower()
              and "raise attorneys" in tri_flat.lower())
        check("SOR/LOI remains the one stated exception",
              "one genuine exception" in tri_flat and "adversarial proceeding" in tri_flat)
        check("'attorney' is not a recommend value any more",
              '"recommend": "fso|support|none"' in tri and "attorney|fso" not in tri)
        check("triage supports the user raising counsel themselves",
              "If the user raises it themselves" in tri_flat)

        for name in ("conductor.md",):
            body = flatten((ROOT / "agents" / name).read_text(encoding="utf-8"))
            check(f"{name} forbids the deferral menu",
                  "never present \"cover it now\"" in body.lower()
                  and "talk to an attorney first" in body.lower())
        td_flat = flatten(td)
        check("thread detector forbids the deferral menu",
              "Do not offer to defer it for legal advice" in td_flat)
        ag = flatten((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        check("the non-negotiable is in the canonical rules file",
              "never offer legal deferral either" in ag.lower())

        print("\nposition_type is derived from scope, never asked")
        s = base_session(); s["position_type"] = "national_security"
        c, o = vs(s, "pt-ok.json")
        check("national_security passes", c == 0, o.strip()[-200:])

        for bad in ("public_trust", "low_risk"):
            s = base_session(); s["position_type"] = bad
            c, o = vs(s, f"pt-{bad}.json")
            check(f"{bad} is rejected — not a clearance-holding population",
                  c == 1 and "clearance holders and applicants only" in o,
                  o.strip()[-200:])

        s = base_session()
        s["out_of_scope_acknowledged"] = True
        s["events"][0]["reporting"]["reportable"] = "yes"
        c, o = vs(s, "pt-oos.json")
        check("no reportability determination for an out-of-scope user",
              c == 1 and "outside this tool's scope" in o, o.strip()[-200:])

        intake_txt = (ROOT / "agents" / "core" / "intake.md").read_text(encoding="utf-8")
        check("intake does not ask for position type",
              "Do not ask about position type" in intake_txt
              and "public trust**, or\n  **low risk**? This selects" not in intake_txt)
        check("intake carries a scope check for non-clearance users",
              "Scope check" in intake_txt and "suitability" in intake_txt)

        print("\nportability — the rules must be tool-neutral and single-source")
        agents_txt = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        claude_txt = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        check("AGENTS.md exists and carries the non-negotiables",
              "John Doe" in agents_txt and "Never fetch" in agents_txt
              and "yes` or `consult_fso" in agents_txt)
        check("CLAUDE.md imports AGENTS.md rather than copying it",
              "@AGENTS.md" in claude_txt)
        # If CLAUDE.md restated the rules, the two would drift the moment one
        # was edited — the same failure the conductor/PROCESS check guards.
        check("CLAUDE.md does not duplicate the rule text",
              len(claude_txt.splitlines()) < 60
              and "Never accept classified information" not in claude_txt,
              f"CLAUDE.md is {len(claude_txt.splitlines())} lines")
        check("AGENTS.md tells non-Claude tools how to load it",
              "Codex" in agents_txt and "Cursor" in agents_txt
              and "plain chat" in agents_txt.lower())
        # A .claude/ file is a convenience, never a dependency. Nothing outside
        # that folder may require it.
        offenders = []
        for f in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "agents").rglob("*.md")):
            body = f.read_text(encoding="utf-8", errors="replace")
            if ".claude/" in body or ".claude\\" in body:
                offenders.append(str(f.relative_to(ROOT)))
        check("no script or agent prompt depends on .claude/", not offenders,
              f"these reference it: {offenders}")

        print("\nrendered process map must not be stale")
        # The failure this catches: PROCESS.md gets updated, docs/process-map.html
        # does not, and the picture someone actually LOOKS at silently describes
        # a version of the tool that no longer exists.
        rendered = ROOT / "docs" / "process-map.html"
        check("docs/process-map.html exists", rendered.exists(),
              "run: python scripts/render_process_map.py")
        if rendered.exists():
            import re as _re
            pm = (ROOT / "PROCESS.md").read_text(encoding="utf-8")
            rh = rendered.read_text(encoding="utf-8")
            src_titles = [_re.sub(r"^\d+\.\s*", "", l[3:].strip())
                          for l in pm.splitlines() if l.startswith("## ")]
            check("every PROCESS.md section appears in the rendered page",
                  all(t_ in rh for t_ in src_titles),
                  f"missing: {[t_ for t_ in src_titles if t_ not in rh]}")
            check("rendered page carries as many diagrams as the source",
                  rh.count('class="mermaid"') == pm.count("```mermaid"),
                  f"{rh.count(chr(39)+chr(39))} vs source {pm.count('```mermaid')}")
            # Spot-check content that only exists after this session's changes.
            for marker, why in (("SF-86 is the collection standard", "form standard"),
                                ("Prior disclosure check", "prior-disclosure branch"),
                                ("arresting agency if different", "entity capture"),
                                ("never offers legal deferral", "no-deferral rule")):
                check(f"rendered map reflects the {why}", marker in rh,
                      "docs/process-map.html is stale — re-run the renderer")

            # ---- Continuous-document structure. The page used to emit
            # seventeen .slide blocks; every seam was a decision about where a
            # reader had to stop, and none came from the content. These checks
            # assert the document flows and does not regress into a deck.
            check("no slide/page chrome survives",
                  'class="slide"' not in rh and 'class="badge"' not in rh
                  and 'class="runfoot"' not in rh,
                  "the map is a document, not a deck")
            check("one section element per PROCESS.md section",
                  rh.count("<section id=") == len(src_titles))
            for i in range(1, len(src_titles) + 1):
                check(f"section {i:02d} is anchored and numbered",
                      f'<section id="s{i}">' in rh
                      and f'<span class="n">{i:02d}</span>' in rh)
            check("every section carries a kicker", rh.count('class="kicker"')
                  >= len(src_titles) + 1)
            check("every section has a declared standfirst",
                  rh.count('class="standfirst"') == len(src_titles),
                  "add '| standfirst: ...' to that section's metadata comment "
                  "in PROCESS.md — the renderer does not guess one")
            check("figures are semantic <figure> elements",
                  rh.count("<figure>") == rh.count('class="mermaid"'))
            check("multi-figure sections number their figures",
                  "Figure 1.1 of 4" in rh,
                  "section 1 has four diagrams and they must be labelled")
            check("masthead and boundary are present",
                  "<h1>" in rh and 'class="boundary"' in rh
                  and "not affiliated with" in rh.lower())
            check("a contents list is generated", 'class="contents"' in rh)
            check("prose flows in the section rather than in a card",
                  'class="card"' not in rh and 'class="prose"' not in rh)

            # Print rules exist because a printed page cannot scroll. Without
            # them a 10:1 flowchart is cut off at the page edge.
            # Sections must NOT force a page break. Six sections meant six
            # fresh pages, and any section running just over a page left most of
            # the next one blank — the largest single source of white space in
            # the printed file.
            check("print CSS protects figures from splitting",
                  "@media print" in rh and "break-inside:avoid" in rh)
            check("sections do NOT force a page break",
                  "break-before:page" not in rh,
                  "content must flow; the printer breaks where the text runs out")
            check("the print page is a real paper size",
                  "size:letter landscape" in rh and "margin:11mm" in rh)
            check("prose runs in columns so the width is not wasted",
                  'class="cols"' in rh and "columns:2" in rh)
            check("figures are NOT inside the column flow",
                  ">figure" not in rh.replace(" ", "")
                  .split('class="cols"')[1].split("</div>")[0]
                  if 'class="cols"' in rh else False,
                  "column-span in paged media is unreliable; figures stay outside")
            check("print paper is white, tint reserved for boxes",
                  "html, body { background:#fff; }" in rh)
            check("print CSS scales wide figures instead of clipping them",
                  "max-width:100% !important" in rh)
            check("on screen figures keep natural size and are pannable",
                  "useMaxWidth:false" in rh and 'class="zoom-pane"' in rh
                  and "overflow:hidden" in rh)
            check("every figure gets zoom controls",
                  rh.count('class="zoom-controls"') == rh.count('class="mermaid"'),
                  "a figure with no zoom controls has no way to see it at scale")
            check("zoom only attaches after mermaid actually finishes rendering",
                  "await mermaid.run(" in rh and "startOnLoad:false" in rh,
                  "startOnLoad:true would race initZoom against an SVG that isn't there yet")
            check("print CSS neutralizes any pan/zoom state left over from screen",
                  "transform:none !important" in rh and ".zoom-controls, .zoom-hint { display:none" in rh)

            # Diagram colours must live in the same palette as the page. The
            # dark-theme fills were unreadable once the page went to paper, and
            # a single stale classDef is the kind of thing nobody notices in a
            # diff but everybody notices on screen.
            pm_src = (ROOT / "PROCESS.md").read_text(encoding="utf-8")
            dark_fills = [f for f in ("#5a2d2d", "#2d4a2d", "#2d3a5a",
                                      "#4a3a1a", "#3d3d5a") if f in pm_src]
            check("no dark-theme diagram fills survive in PROCESS.md",
                  not dark_fills, f"stale fills: {dark_fills}")
            check("the renderer themes mermaid to the paper palette",
                  "#FDFBF7" in rh and "theme:'base'" in rh)

        print("\nrender_pdf.py — opt-in, and it says so instead of crashing")
        # Everything else in scripts/ runs on stdlib + PyYAML so a non-developer
        # can run the suite with one command. The PDF needs a headless browser,
        # which is too big to force on someone validating a corpus. So it must
        # degrade with an instruction, never a traceback.
        rp = ROOT / "scripts" / "render_pdf.py"
        check("scripts/render_pdf.py exists", rp.exists())
        if rp.exists():
            rpt = rp.read_text(encoding="utf-8")
            check("it guards its optional imports",
                  "except ImportError" in rpt and "pip install" in rpt)
            check("it is not imported by anything in the repo",
                  not any("render_pdf" in p.read_text(encoding="utf-8")
                          for p in (ROOT / "scripts").glob("*.py")
                          if p.name != "render_pdf.py"))
            check("it explains why the PDF is raster",
                  "not selectable" in rpt)
            c, o = run(rp, "--help")
            check("--help works without the optional dependencies", c == 0,
                  o.strip()[-200:])

        # ------------------------------------------------------------------
        # The reporting axis. Guideline checklists cover what a matter is
        # GRADED against; event checklists cover what the policy requires be
        # REPORTED. They do not line up, and the gap that motivated these
        # tests was real: unofficial foreign travel — the only obligation in
        # the scheme that must be met BEFORE the event — mapped to no
        # guideline and therefore had no questions behind it at all.
        # ------------------------------------------------------------------
        print("\nevent checklists — every reportable event has questions behind it")
        cdir = ROOT / "corpus" / "checklists"
        edir = cdir / "events"
        check("corpus/checklists/events/ exists", edir.is_dir())

        table_ids: dict[str, str] = {}
        for tp in sorted((ROOT / "corpus" / "reporting" / "tables").glob("*.yaml")):
            td = yaml.safe_load(tp.read_text(encoding="utf-8")) or {}
            for entry in td.get("entries") or []:
                if isinstance(entry, dict) and entry.get("id"):
                    table_ids[entry["id"]] = tp.name
        check("reporting tables define reportable events", len(table_ids) >= 20,
              f"found {len(table_ids)}")

        claims: dict[str, list[str]] = {}
        event_files = [p for p in sorted(edir.glob("*.yaml"))
                       if not p.name.startswith("_")]
        for p in event_files:
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            for ev in d.get("event_ids") or []:
                claims.setdefault(ev, []).append(p.name)

        unclaimed = sorted(set(table_ids) - set(claims))
        check("every reportable event id is claimed by an event checklist",
              not unclaimed, f"unclaimed: {unclaimed}")
        dupes = {k: v for k, v in claims.items() if len(v) > 1}
        check("no reportable event is claimed twice", not dupes, f"{dupes}")
        unknown = sorted(set(claims) - set(table_ids))
        check("no event checklist claims an id that is in no table",
              not unknown, f"unknown: {unknown}")

        # The honest-gap rule: a checklist with no citable authority behind it
        # must say so and must not assert an obligation.
        for p in event_files:
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            if not (d.get("event_ids") or []):
                check(f"{p.name} without a table entry explains itself",
                      bool(str(d.get("no_table_entry_because", "")).strip())
                      and d.get("reportability_default") == "consult_fso",
                      "must carry no_table_entry_because and consult_fso")
            for g in d.get("guidelines") or []:
                check(f"{p.name} → guideline {g} checklist exists",
                      (cdir / f"guideline-{g}.yaml").exists())

        print("\ncoverage spine — who/what/when/where/why/how/future intent")
        spec = yaml.safe_load((cdir / "_COVERAGE.yaml").read_text(encoding="utf-8")) or {}
        facets = {f["id"] for f in spec.get("facets", [])}
        required_facets = set(spec.get("required_facets", []))
        inheritable = set(spec.get("inheritable_from_universal", []))
        check("_COVERAGE.yaml defines the seven facets",
              facets == {"who", "what", "when", "where", "why", "how", "future_intent"},
              f"{sorted(facets)}")

        checklists = [p for p in sorted(cdir.glob("*.yaml"))
                      if p.name not in ("_COVERAGE.yaml", "_TEMPLATE.yaml", "_UNIVERSAL.yaml",
                                         "_SEVERITY_LADDERS.yaml", "_DOCUMENT_EVIDENCE.yaml",
                                         "_INCIDENT_CHRONOLOGY.yaml", "_INCIDENT_PROFILES.yaml")]
        for p in checklists + event_files:
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            els = d.get("elements") or []
            untagged = [e.get("id") for e in els
                        if isinstance(e, dict) and e.get("covers") is None]
            check(f"{p.name}: every element declares covers", not untagged,
                  f"untagged: {untagged}")
            check(f"{p.name}: declares how_relevant", "how_relevant" in d)
            got = set()
            for e in els:
                if isinstance(e, dict):
                    got |= set(e.get("covers") or [])
            need = required_facets - inheritable
            if d.get("how_relevant") is False:
                need = need - {"how"}
                check(f"{p.name}: declining 'how' is justified in prose",
                      bool(str(d.get("how_not_relevant_because", "")).strip()))
            check(f"{p.name}: covers every required facet", need <= got,
                  f"missing: {sorted(need - got)}")

        print("\nthe gates bite — a broken corpus must fail, not warn")
        import shutil as _shutil
        neg = tmp / "neg-corpus"
        _shutil.copytree(ROOT / "corpus", neg)
        # Leave a reportable event with no questions behind it.
        cp = neg / "checklists" / "events" / "event-crypto.yaml"
        cp.write_text(cp.read_text(encoding="utf-8").replace(
            "event_ids: [adv.crypto.foreign]", "event_ids: [adv.crypto.foreign_TYPO]"),
            encoding="utf-8")
        # Misspell a facet, which satisfies nothing and hides the gap.
        lp = neg / "checklists" / "guideline-L.yaml"
        lp.write_text(lp.read_text(encoding="utf-8").replace(
            "covers: [what]\n", "covers: [whaat]\n", 1), encoding="utf-8")
        # Say nothing about whether mechanism applies.
        ap = neg / "checklists" / "guideline-A.yaml"
        ap.write_text(ap.read_text(encoding="utf-8").replace(
            "how_relevant: true\n", "", 1), encoding="utf-8")
        c, o = run(VALIDATE, "--corpus", str(neg))
        check("broken corpus fails validation", c == 1, o.strip()[-200:])
        for frag, why in (
            ("claimed by no event checklist", "unclaimed reportable event"),
            ("is not a facet in _COVERAGE.yaml", "misspelled coverage facet"),
            ("must declare how_relevant", "undeclared mechanism relevance"),
            ("is in no reporting table", "event id with no table entry"),
        ):
            check(f"validator names the {why}", frag in o, o.strip()[-400:])

        print("\nsession gate — a malformed event id in 'basis' is caught")
        # basis does two jobs: it cites the obligation and it selects the event
        # checklist. A near-miss id selects nothing and nothing downstream
        # notices, so the near-miss has to fail here.
        s = base_session()
        sp = tmp / "evids.json"
        for bad in (["aci.Travel.Unofficial"], ["aci..travel"], [""]):
            s["events"][0].setdefault("reporting", {})["basis"] = bad
            sp.write_text(json.dumps(s), encoding="utf-8")
            c, o = run(VALSESS, str(sp))
            check(f"session with basis={bad} is rejected", c == 1, o.strip()[-200:])
        s["events"][0]["reporting"]["basis"] = ["aci.travel.unofficial"]
        sp.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VALSESS, str(sp))
        check("session with a well-formed event id is accepted", c == 0, o.strip()[-200:])
        # A non-id citation is legitimate and must not be broken by the check.
        s["events"][0]["reporting"]["basis"] = ["SF-86 Section 22 question"]
        sp.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VALSESS, str(sp))
        check("a non-id citation in basis still passes", c == 0, o.strip()[-200:])

        print("\nthe no-legal-deferral rule survived the rewrite")
        # An earlier draft of guideline-D told the interviewer to advise
        # consulting an attorney. That is exactly the behaviour the tool is
        # not permitted to have: the user already decided to disclose.
        for p in checklists + event_files:
            body = p.read_text(encoding="utf-8").lower()
            check(f"{p.name} does not offer legal deferral",
                  "consult an attorney" not in body
                  and "talk to a lawyer" not in body
                  and "speak to an attorney" not in body,
                  "checklists never route the user to counsel")

        print("\nconductor.md ↔ PROCESS.md drift check")
        ok, why = check_anchor_order(ROOT / "agents" / "conductor.md",
                                     CONDUCTOR_ANCHORS)
        check("conductor.md stages present and in canonical order", ok, why)
        ok, why = check_anchor_order(ROOT / "PROCESS.md", PROCESS_ANCHORS)
        check("PROCESS.md stages present and in canonical order", ok, why)

        print("\nscore_evals.py — the scorer itself is tested")
        rdir = tmp / "evals"
        rdir.mkdir()
        good = {
            "reportable": "yes", "channel_family": "industry",
            "guidelines": ["G", "J"], "e_attach": False,
            "delay_explanation_needed": False, "timeliness_warning": True,
            "threads": [], "notes_to_user": "Contact your FSO today.",
        }
        (rdir / "owi-industry-holder.result.json").write_text(
            json.dumps(good), encoding="utf-8")
        c, o = run(SCORE, "--only", "owi-industry-holder",
                   "--results-dir", str(rdir))
        check("correct eval result passes", c == 0, o.strip()[-300:])

        bad = dict(good)
        bad["reportable"] = "no"
        bad["guidelines"] = ["G"]
        (rdir / "owi-industry-holder.result.json").write_text(
            json.dumps(bad), encoding="utf-8")
        c, o = run(SCORE, "--only", "owi-industry-holder",
                   "--results-dir", str(rdir))
        check("reportable='no' and missing guideline fail the eval",
              c == 1 and "never" in o.lower() and "missing" in o.lower(),
              o.strip()[-300:])

        c, o = run(SCORE, "--only", "federal-never-diss",
                   "--results-dir", str(rdir))
        check("missing result file fails the eval", c == 1 and "missing" in o.lower())

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
