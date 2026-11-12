#!/usr/bin/env python3
"""Edge cases for the three deterministic gates: validate_session.py,
assemble_package.py and verify_output.py, plus the privacy floor they share.

tests/run_tests.py exercises each gate's main path. This file goes after
what that leaves open: malformed and missing input, every validator branch,
and the absolutes no privacy tier relaxes. Pure checks call the gate
functions directly; anything defined by exit code or stdout runs the script.

Plain Python, no test framework. Every value is synthetic, and every
SSN-shaped string uses an area number (000) the SSA never issues.

Usage:  python tests/run_gate_tests.py
Exit:   0 all passed · 1 something failed
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
MINI = ROOT / "tests" / "fixtures" / "mini-library"
os.environ["AIA_LIBRARY"] = str(MINI)  # hermetic: never the machine's real library

import assemble_package  # noqa: E402
import validate_session as vs  # noqa: E402
import verify_output as vo  # noqa: E402

ASSEMBLE = SCRIPTS / "assemble_package.py"
VERIFY = SCRIPTS / "verify_output.py"
VALSESS = SCRIPTS / "validate_session.py"

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def run(script: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(script), *args], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=300)
    return r.returncode, r.stdout + r.stderr


def phases(**override) -> dict:
    base = {
        "before": "I was at a restaurant before driving.",
        "precipitating_circumstances": "I drank alcohol before deciding to drive.",
        "decisions_and_actions": "I left and drove.",
        "incident": "I was stopped and arrested for OWI.",
        "immediate_aftermath": "A breath test reported 0.16.",
        "later_consequences": "A criminal court matter followed.",
        "current_status": "The incident is being reported.",
        "future_developments": "The court disposition may follow later.",
    }
    out = {k: {"status": "answered", "evidence": v} for k, v in base.items()}
    out.update(override)
    return out


def session() -> dict:
    """A complete, valid holder session with one developed incident."""
    return {
        "privacy_tier": "medium",
        "population": "industry",
        "role": "holder",
        "form": "sf86",
        "access_tier": "baseline",
        "position_type": "national_security",
        "final_analysis_complete": True,
        "stage_log": [{"stage": "intake"}, {"stage": "final_analysis"}],
        "events": [{
            "title": "Alcohol-related arrest",
            "guidelines": ["G", "J"],
            "incident_development": {"profiles": ["impaired-driving"], "complete": True, "phases": phases()},
            "incident_types": ["Alcohol Consumption", "Criminal Conduct"],
            "future_update_topics": ["Any later court disposition"],
            "narrative": "I was arrested in June 2026 for operating while intoxicated.",
            "reporting": {"reportable": "yes", "basis": ["aci.criminal.arrest"]},
        }],
    }


def errors_for(mutate) -> list[str]:
    s = session()
    mutate(s)
    return vs.validate(s)[0]


def has(errors: list[str], needle: str) -> bool:
    return any(needle.lower() in e.lower() for e in errors)


@contextlib.contextmanager
def fresh_verifier():
    """verify_output keeps module-level failure and note lists; reset them."""
    vo.failures.clear()
    vo.notes.clear()
    try:
        yield vo.failures
    finally:
        vo.failures.clear()
        vo.notes.clear()


def pii_failures(text: str, tier: str = "high", entities: list | None = None) -> list[str]:
    with fresh_verifier() as f:
        vo.check_pii(text, tier, entities or [])
        return list(f)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        print("\nvalidate_session.validate — a complete session")
        errs, warns = vs.validate(session())
        check("the reference session is clean", errs == [] and warns == [], f"{errs} {warns}")

        print("\nvalidate_session.validate — enums and scope")
        check("a missing privacy tier is an error", has(errors_for(lambda s: s.pop("privacy_tier")), "missing required field 'privacy_tier'"))
        for field, bad in (("population", "contractor"), ("role", "in-process"), ("form", "SF86"), ("access_tier", "secret")):
            check(f"{field}={bad!r} is outside its enum", has(errors_for(lambda s, f=field, b=bad: s.__setitem__(f, b)), f"'{field}' is"))
        check("position_type other than national_security is refused",
              has(errors_for(lambda s: s.__setitem__("position_type", "public_trust")), "position_type"))
        check("an out-of-scope user gets no reportability determination",
              has(errors_for(lambda s: s.__setitem__("out_of_scope_acknowledged", True)), "outside this tool's scope"))
        s = session(); s["privacy_tier"] = "high"; s["mapping_notice_delivered"] = True
        errs, warns = vs.validate(s)
        check("a high-tier flag with no recorded confirmation is a warning, not silence",
              errs == [] and any("mapping_notice" in w for w in warns), f"{errs} {warns}")

        print("\nvalidate_session.validate — narrative integrity")
        check("a non-string narrative is refused", has(errors_for(lambda s: s.__setitem__("narrative", ["I", "did"])), "must be a string"))
        check("a stamp without a narrative is refused",
              has(errors_for(lambda s: s.__setitem__("narrative_sha256", "0" * 64)), "'narrative' is missing"))
        s = session(); s["narrative"] = "I was arrested."
        check("an unstamped narrative is a warning", any("unstamped" in w for w in vs.validate(s)[1]))
        s["narrative_sha256"] = vs.narrative_hash("I was arrested.")
        check("a matching stamp passes", vs.validate(s)[0] == [])
        s["narrative"] = "I was arrested. "
        check("one trailing space is an alteration", has(vs.validate(s)[0], "NARRATIVE ALTERED"))

        print("\nvalidate_session.validate — the privacy floor (fake values only)")
        for label, text in (("SSN", "I gave them 000-12-3456."), ("DOB", "DOB: 01/02/1980"),
                            ("marking", "It read TOP SECRET//SCI.")):
            errs = errors_for(lambda s, t=text: s.__setitem__("narrative", t))
            check(f"a narrative holding a {label} is an error", has(errs, "contains what looks like"), str(errs))
            check(f"the {label} error names the kind, never the value", not any(text.split()[-1].rstrip(".") in e for e in errs), str(errs))
        errs = errors_for(lambda s: s.__setitem__("user_confirmations", {"mapping_notice": "yes 000-12-3456"}))
        check("a recorded confirmation holding an SSN is an error", has(errs, "user_confirmations.mapping_notice"), str(errs))
        check("a narrative that describes a Secret document is fine",
              errors_for(lambda s: s.__setitem__("narrative", "I left a Secret document on my desk.")) == [])
        check("non-dict user_confirmations are not crawled", errors_for(lambda s: s.__setitem__("user_confirmations", "000-12-3456")) == [])

        print("\nvalidate_session.validate — events")
        check("events must be a list", has(errors_for(lambda s: s.__setitem__("events", {"0": {}})), "'events' must be a list"))
        check("events need a route", has(errors_for(lambda s: s.pop("role")), "'role' is missing"))
        check("final analysis with no incidents is refused",
              has(errors_for(lambda s: s.__setitem__("events", [])), "no incidents exist"))
        check("an event must be an object", has(errors_for(lambda s: s["events"].append("text")), "must be an object"))
        check("guideline letters are A through M", has(errors_for(lambda s: s["events"][0].__setitem__("guidelines", ["N"])), "invalid guideline"))
        check("incident_types must be a list",
              has(errors_for(lambda s: s["events"][0].__setitem__("incident_types", "Criminal Conduct")), "incident_types must be a list"))
        check("an applicant's incident carries no DISS types",
              has(errors_for(lambda s: s.__setitem__("role", "applicant")), "form crosswalks, not DISS"))
        check("future update topics cannot be blank",
              has(errors_for(lambda s: s["events"][0].__setitem__("future_update_topics", ["  "])), "future_update_topics"))
        check("a third-person completed narrative is refused",
              has(errors_for(lambda s: s["events"][0].__setitem__("narrative", "The subject was arrested.")), "first-person voice"))

        print("\nvalidate_session.validate — incident development")
        check("profiles must be a non-empty list",
              has(errors_for(lambda s: s["events"][0]["incident_development"].__setitem__("profiles", [])), "non-empty list"))
        check("phases must be an object",
              has(errors_for(lambda s: s["events"][0]["incident_development"].__setitem__("phases", [])), "phases must be an object"))
        check("a phase record must be an object",
              has(errors_for(lambda s: s["events"][0]["incident_development"]["phases"].__setitem__("before", "yes")), "before must be an object"))
        check("a phase status outside the set is refused",
              has(errors_for(lambda s: s["events"][0]["incident_development"]["phases"]["before"].__setitem__("status", "skipped")), "status must be one of"))
        check("a phase with no evidence is refused",
              has(errors_for(lambda s: s["events"][0]["incident_development"]["phases"]["before"].__setitem__("evidence", "")), "evidence is required"))
        check("not_applicable needs a concrete reason, not 'N/A'",
              has(errors_for(lambda s: s["events"][0]["incident_development"]["phases"].__setitem__(
                  "future_developments", {"status": "not_applicable", "evidence": "N/A"})), "concrete reason"))
        check("a declined phase must be listed in declined_elements",
              has(errors_for(lambda s: s["events"][0]["incident_development"]["phases"].__setitem__(
                  "before", {"status": "declined", "evidence": "The user declined."})), "declined_elements"))
        check("development must be marked complete",
              has(errors_for(lambda s: s["events"][0]["incident_development"].__setitem__("complete", False)), "complete must be true"))

        print("\nvalidate_session.validate — reporting, prior disclosure, crosswalk")
        check("reportable outside yes/consult_fso names the allowed values",
              has(errors_for(lambda s: s["events"][0]["reporting"].__setitem__("reportable", "maybe")), "must be one of ['consult_fso', 'yes']"))
        check("basis must be a list",
              has(errors_for(lambda s: s["events"][0]["reporting"].__setitem__("basis", "aci.criminal.arrest")), "basis must be a list"))
        check("a blank basis entry is refused",
              has(errors_for(lambda s: s["events"][0]["reporting"].__setitem__("basis", [""])), "not a non-empty string"))
        for bad in ("aci..criminal", "ACI.Criminal.Arrest", "aci.criminal."):
            check(f"malformed event id {bad!r} is refused",
                  has(errors_for(lambda s, b=bad: s["events"][0]["reporting"].__setitem__("basis", [b])), "malformed"))
        check("prior_disclosure needs a known status",
              has(errors_for(lambda s: s["events"][0].__setitem__("prior_disclosure", {"status": "told_them"})), "prior_disclosure.status"))
        check("no-new-obligation relief needs a prior-disclosure record",
              has(errors_for(lambda s: s["events"][0]["reporting"].__setitem__("no_new_obligation_identified", True)), "no prior_disclosure record"))
        check("a crosswalk entry must be an object",
              has(errors_for(lambda s: s["events"][0].__setitem__("crosswalk", ["22"])), "crosswalk[0]: must be an object"))
        check("a crosswalk field status outside the set is refused",
              has(errors_for(lambda s: s["events"][0].__setitem__("crosswalk", [{"fields": [{"id": "x", "status": "tbd"}]}])), "status is 'tbd'"))
        check("a date field cannot carry both a status and an answer",
              has(errors_for(lambda s: s["events"][0].__setitem__("crosswalk", [{"fields": [
                  {"id": "offense_date", "status": "pending", "answer": "June 2026"}]}])), "must not also carry an answer"))
        check("a person entry needs a label",
              has(errors_for(lambda s: s["events"][0].__setitem__("persons", [{"role": "my supervisor"}])), "needs a 'label'"))
        check("an outstanding item needs an element",
              has(errors_for(lambda s: s.__setitem__("outstanding_required", [{"how_to_get": "ask"}])), "needs an 'element'"))

        print("\nvalidate_session.validate — stage log")
        check("stage_log must be a list", has(errors_for(lambda s: s.__setitem__("stage_log", "intake")), "'stage_log' must be a list"))
        check("an unknown stage is refused", has(errors_for(lambda s: s["stage_log"].append({"stage": "vibes"})), "unknown or missing stage"))
        check("a shrunken log is refused",
              has(errors_for(lambda s: s.__setitem__("stage_log_length_at_last_validate", 5)), "SHRANK"))

        print("\nvalidate_session.py — command line")
        c, o = run(VALSESS)
        check("no arguments prints usage and exits 1", c == 1 and "usage" in o.lower(), o)
        c, o = run(VALSESS, str(tmp / "absent.json"))
        check("a missing file exits 1", c == 1 and "not found" in o, o)
        bad = tmp / "bad.json"
        bad.write_text("{oops", encoding="utf-8")
        c, o = run(VALSESS, str(bad))
        check("invalid JSON exits 1 with a FAIL line, no traceback", c == 1 and "not valid JSON" in o and "Traceback" not in o, o)
        p = tmp / "s.json"
        s = session()
        p.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VALSESS, str(p))
        check("a sound session exits 0 and records the log length",
              c == 0 and json.loads(p.read_text(encoding="utf-8"))["stage_log_length_at_last_validate"] == 2, o)
        s["privacy_tier"] = "maximum"
        p.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VALSESS, str(p))
        check("an unsound session exits 1 and the file is not rewritten",
              c == 1 and "stage_log_length_at_last_validate" not in json.loads(p.read_text(encoding="utf-8")), o)
        s = session()
        p.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VALSESS, str(p), "--stamp-narrative")
        check("stamping with no narrative is refused", c == 1 and "cannot stamp" in o, o)
        s = session(); s["narrative"] = "I was arrested. My SSN is 000-12-3456."
        p.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(VALSESS, str(p), "--stamp-narrative")
        on_disk = json.loads(p.read_text(encoding="utf-8"))
        check("a narrative breaching the floor is never stamped",
              c == 1 and "cannot stamp" in o and "narrative_sha256" not in on_disk, o)
        check("and the refusal does not print the value", "000-12-3456" not in o, o)

        print("\nverify_output — privacy absolutes hold at every tier")
        for tier in ("low", "medium", "high"):
            check(f"a hyphenated SSN fails at tier {tier}", any("SSN" in f for f in pii_failures("Mine is 000-12-3456.", tier)))
            check(f"a labeled date of birth fails at tier {tier}", any("Date-of-birth" in f for f in pii_failures("DOB: 01/02/1980", tier)))
        # The floor's other shapes. Before privacy_floor.py the verifier knew
        # only the hyphenated SSN and three DOB labels, and no markings at all.
        for label, text in (("a spaced SSN", "Number 000 12 3456."), ("a dotted SSN", "Number 000.12.3456."),
                            ("a labeled nine-digit SSN", "SSN: 000123456"),
                            ("a Social Security No. label", "Social Security No. 000123456")):
            check(f"{label} fails at tier low", any("SSN" in f for f in pii_failures(text, "low")), label)
        for label, text in (("D.O.B.", "D.O.B. 01/02/1980"), ("birthdate", "birthdate: 01/02/1980"),
                            ("birth date in words", "birth date January 2, 1980")):
            check(f"a DOB labeled {label} fails", any("Date-of-birth" in f for f in pii_failures(text, "low")), label)
        for label, text in (("a banner", "The page read TOP SECRET//SCI."), ("a short portion banner", "Marked S//NF."),
                            ("a portion mark", "Quoted:\n(S) The fictional office moved."),
                            ("a classification authority line", "Declassify On: 20450101")):
            for tier in ("low", "high"):
                check(f"{label} fails at tier {tier}", any("Classification marking" in f for f in pii_failures(text, tier)), label)
        check("a plain description of a classified document passes",
              pii_failures("I left a Secret document and a TS/SCI badge on my desk.", "high") == [])
        msgs = " ".join(pii_failures("SSN 000-12-3456, DOB: 01/02/1980, SECRET//NOFORN", "low"))
        check("absolute failures never echo the value",
              msgs and not any(v in msgs for v in ("000-12-3456", "01/02/1980", "NOFORN")), msgs)
        check("the package's own privacy boilerplate is not a date of birth",
              pii_failures(assemble_package.privacy_header("high"), "high") == [])
        check("an incident date is not a date of birth", pii_failures("I was arrested on 3 March 2026.", "high") == [])

        print("\nverify_output — tier-dependent identifiers")
        check("a phone number is allowed at tier low", pii_failures("Call 555-867-5309.", "low") == [])
        check("a phone number fails at tier medium", any("phone" in f for f in pii_failures("Call 555-867-5309.", "medium")))
        check("an email fails at tier medium", any("email" in f for f in pii_failures("Write to someone@example.com.", "medium")))
        check("an email is allowed at tier low", pii_failures("Write to someone@example.com.", "low") == [])
        bar = [{"name": "The Blue Heron Tavern", "phone": "555-867-5309", "confirmed_by_user": True}]
        check("a confirmed business phone is exempt at tier high", pii_failures("Call 555-867-5309.", "high", bar) == [])
        unconfirmed = [{**bar[0], "confirmed_by_user": False}]
        check("an unconfirmed business phone is not exempt", any("phone" in f for f in pii_failures("Call 555-867-5309.", "high", unconfirmed)))
        with fresh_verifier() as f:
            vo.check_entities("It is at 9 Fictional Way.", [{"name": "Bar", "address": "9 Fictional  Way", "confirmed_by_user": False}])
            check("an unconfirmed entity address in the package fails, whitespace-insensitively", any("never confirmed" in x for x in f), str(f))

        print("\nverify_output — structure and wording")
        with fresh_verifier() as f:
            check("an unknown tier fails and is verified at the strictest", vo.check_tier_declared({"privacy_tier": "maximum"}) == "high" and f)
        with fresh_verifier() as f:
            check("no session means the strictest tier", vo.check_tier_declared(None) == "high" and not f and vo.notes)
        with fresh_verifier() as f:
            vo.check_pseudonym("Prepared for Jane.")
            check("a package without John Doe fails", any("John Doe" in x for x in f))
        with fresh_verifier() as f:
            vo.check_required("John Doe. Not affiliated with anyone.")
            check("a missing adjudication disclaimer fails", any("adjudication disclaimer" in x for x in f), str(f))
        with fresh_verifier() as f:
            vo.check_version("Corpus version: 0.0.0-other", ROOT / "corpus")
            check("a package from another corpus version fails", any("not recorded" in x for x in f), str(f))
        with fresh_verifier() as f:
            vo.check_version("anything", tmp)
            check("a corpus with no VERSION file is noted, not silently passed", not f and any("VERSION" in n for n in vo.notes))
        with fresh_verifier() as f:
            vo.check_persons("Person 1 knew.")
            check("a Person reference with no template fails", any("completion template" in x for x in f), str(f))
        for phrase in ("you are likely to be granted", "Your odds are good", "it will probably work out",
                       "most cases like this end well", "this is typically granted",
                       "I recommend not reporting this", "you do not need to report the arrest",
                       "omit the DUI from your report", "wait until the court date before reporting"):
            with fresh_verifier() as f:
                vo.check_banned(phrase)
                check(f"banned: {phrase!r}", bool(f))
        with fresh_verifier() as f:
            vo.check_banned("I reported the arrest promptly. The Government makes all determinations.")
            check("ordinary reporting language is not banned", not f, str(f))
        sp = tmp / "out.json"
        sp.write_text(json.dumps({"outstanding_required": [{"element": "court-disposition"}]}), encoding="utf-8")
        with fresh_verifier() as f:
            vo.check_outstanding("## STILL REQUIRED\n- something else", sp)
            check("a STILL REQUIRED section that omits an outstanding element fails", any("court-disposition" in x for x in f), str(f))

        print("\nverify_output.py — command line")
        c, o = run(VERIFY, str(tmp / "absent.md"))
        check("a missing package exits 1", c == 1 and "not found" in o, o)
        u16 = tmp / "utf16.md"
        u16.write_bytes("# John Doe\n".encode("utf-16"))
        c, o = run(VERIFY, str(u16))
        check("a UTF-16 package (PowerShell redirection) is refused with the fix", c == 1 and "-o" in o and "UTF-8" in o, o)
        vs_path, vpkg = tmp / "v.json", tmp / "v.md"
        vs_path.write_text(json.dumps(session()), encoding="utf-8")
        c, o = run(ASSEMBLE, str(vs_path), "-o", str(vpkg))
        c, o = run(VERIFY, str(vpkg), str(vs_path))
        check("an assembled reference package verifies", c == 0 and "PASS" in o, o[-300:])
        clean = vpkg.read_text(encoding="utf-8")
        for label, planted in (("a portion-marked paragraph", "\n(S) The fictional program office moved.\n"),
                               ("a spaced SSN", "\nThe form number was 000 12 3456.\n")):
            vpkg.write_text(clean + planted, encoding="utf-8")
            c, o = run(VERIFY, str(vpkg), str(vs_path))
            check(f"a package with {label} does not ship", c == 1 and "DO NOT DELIVER" in o, o[-300:])
        vpkg.write_text(clean, encoding="utf-8")

        print("\nassemble_package.py — refusals")
        sp = tmp / "asm.json"
        s = session(); s["final_analysis_complete"] = False
        sp.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(ASSEMBLE, str(sp), "-o", str(tmp / "p.md"))
        check("assembly waits for the final combined analysis", c == 1 and "final_analysis_complete" in o and not (tmp / "p.md").exists(), o)
        s = session(); s["events"][0]["incident_development"]["complete"] = False
        sp.write_text(json.dumps(s), encoding="utf-8")
        c, o = run(ASSEMBLE, str(sp), "-o", str(tmp / "p.md"))
        check("assembly refuses an undeveloped incident", c == 1 and "incident development" in o, o)
        unversioned = tmp / "corpus-no-version"
        shutil.copytree(ROOT / "corpus", unversioned)
        (unversioned / "VERSION").unlink()
        sp.write_text(json.dumps(session()), encoding="utf-8")
        c, o = run(ASSEMBLE, str(sp), "-o", str(tmp / "p.md"), "--corpus", str(unversioned))
        check("a corpus with no VERSION refuses an untraceable package", c == 1 and "VERSION" in o and not (tmp / "p.md").exists(), o)
        empty = tmp / "empty-folder"
        empty.mkdir()
        c, o = run(ASSEMBLE, str(sp), "-o", str(tmp / "p.md"), "--corpus", str(empty))
        check("a folder that is not a corpus is refused, never treated as an empty one",
              c != 0 and "does not look like the corpus" in o and not (tmp / "p.md").exists(), o)
        c, o = run(ASSEMBLE, str(sp))
        check("without -o the package goes to stdout with the UTF-16 warning",
              c == 0 and "WARNING: no -o" in o and "John Doe" in o, o[-300:])

        print("\nassemble_package — rendering")
        s = session(); s["role"] = "in_process"; s["events"][0].pop("incident_types")
        check("in-process output routes through the sponsoring office",
              "sponsoring" in assemble_package.submission_route(s))
        check("an unknown tier gets no privacy header rather than a wrong one", assemble_package.privacy_header("maximum") == "")
        req = assemble_package.outstanding_required([{"element": "court-disposition", "source_ref": "SF-86 §22", "how_to_get": "Ask the clerk."}])
        check("a STILL REQUIRED item renders its element, source and how to get it",
              "**court-disposition** — SF-86 §22" in req and "Ask the clerk." in req and "Do not delay" in req)
        check("no outstanding items renders nothing", assemble_package.outstanding_required([]) == "")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
