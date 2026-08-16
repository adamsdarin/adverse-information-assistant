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
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ASSEMBLE = ROOT / "scripts" / "assemble_package.py"
VERIFY = ROOT / "scripts" / "verify_output.py"
VALSESS = ROOT / "scripts" / "validate_session.py"
SCORE = ROOT / "scripts" / "score_evals.py"
CHECKLIB = ROOT / "scripts" / "check_library.py"
RETRIEVAL = ROOT / "scripts" / "doha_retrieval.py"
COURTS = ROOT / "scripts" / "court_lookup.py"

# Drift check: conductor.md is the generative source of the session flow and
# PROCESS.md renders it. These two anchor lists encode the SAME canonical
# stage order, expressed in each file's own vocabulary. If either file
# reorders or drops a stage, its anchors stop appearing in this order and the
# check fails — forcing whoever edits one file to look at the other.
CONDUCTOR_ANCHORS = [
    "**Locate the reference material**", "**Capability canary", "**Intake**", "**Triage",
    "**Reporting obligation", "**Adjudicative criteria**",
    "**Question sourcing**", "**Gap loop**", "**Thread detection",
    "**Consistency**", "**Documents**", "**Narrative**", "**Candor**",
    "**Assemble**", "**Verify**", "**Handoff**",
]
PROCESS_ANCHORS = [
    "0 · Locate reference material", "0b · Capability canary",
    "1 · Intake", "<b>Open narrative</b>", "① Requirements Advisor",
    "② Classifier", "<b>Pace choice</b>", "<b>Question sourcing</b>",
    "<b>Gap → Interview loop</b>", "<b>Thread Detector</b>",
    "<b>Consistency Checker</b>", "<b>Documents Advisor</b>",
    "<b>Narrative Writer</b>", "<b>Candor Reviewer</b>",
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


def run(script: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True)
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
