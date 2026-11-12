#!/usr/bin/env python3
"""End-to-end tests for the Phase 1–2 product shell (adverse_app/).

Covers the engine (core.py), the command line (cli.py, scripts/adverse.py,
python -m adverse_app) and the narrow local MCP facade (mcp_server.py). The
MCP SDK is optional and usually not installed, so the facade is exercised
against a stub FastMCP that records every registration; when the real SDK is
importable the same allowlist is also checked through it.

Plain Python, no test framework. Every value is synthetic.

Usage:  python tests/run_product_tests.py
Exit:   0 all passed · 1 something failed
"""
from __future__ import annotations

import contextlib
import hashlib
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adverse_app import cli, core  # noqa: E402

ADVERSE = ROOT / "scripts" / "adverse.py"
# Hermetic: every gate the engine runs resolves the synthetic mini-library,
# never whatever real DCSA Library this machine happens to have installed.
os.environ["AIA_LIBRARY"] = str(ROOT / "tests" / "fixtures" / "mini-library")
# The six tools docs/HOSTED-MCP-DESIGN.md §2.1 names for the local facade.
LOCAL_MCP_TOOLS = {
    "session_status", "next_intake_question", "answer_intake_question",
    "validate_session", "assemble_package", "verify_package",
}

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


def raises(fn, *args, **kwargs) -> str | None:
    """Return the SessionError message fn raises, or None if it does not."""
    try:
        fn(*args, **kwargs)
    except core.SessionError as exc:
        return str(exc)
    return None


def adverse(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ADVERSE), *args], cwd=ROOT,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)


def cli_main(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(list(argv))
        except SystemExit as exc:  # argparse
            code = exc.code
    return code, out.getvalue(), err.getvalue()


INTAKE = ["industry", "holder", "sf-86", "secret",
          "A fictional OWI happened in June. No classified information is included."]


def intake(path: Path, privacy: str = "medium") -> None:
    core.start(path, privacy, force=True)
    for answer in INTAKE:
        core.answer_intake(answer, path)


def complete_event() -> dict:
    """One fully developed, synthetic holder incident that clears every gate."""
    phases = {
        "before": "I was at a restaurant before driving.",
        "precipitating_circumstances": "I drank alcohol before deciding to drive.",
        "decisions_and_actions": "I left and drove.",
        "incident": "I was stopped and arrested for OWI.",
        "immediate_aftermath": "A breath test reported 0.16.",
        "later_consequences": "A criminal court matter followed.",
        "current_status": "The incident is being reported.",
        "future_developments": "The court disposition may follow later.",
    }
    return {
        "title": "Alcohol-related arrest",
        "guidelines": ["G", "J"],
        "incident_development": {
            "profiles": ["impaired-driving", "arrest-or-criminal-process"],
            "complete": True,
            "phases": {k: {"status": "answered", "evidence": v} for k, v in phases.items()},
        },
        "incident_types": ["Alcohol Consumption", "Criminal Conduct"],
        "future_update_topics": ["Any later court disposition or change in charges"],
        "narrative": "I was arrested in June 2026 for operating while intoxicated. My breath test reported 0.16.",
        "reporting": {"reportable": "yes", "channel": "FSO -> DISS incident report",
                      "timeline": "promptly", "basis": ["aci.criminal.arrest"]},
        "documents": [{"name": "Certified court disposition", "source": "Clerk of court", "timing": "can_follow"}],
    }


def complete_session(path: Path) -> None:
    """Intake, then the specialist stages the host model would have run."""
    intake(path)
    data = core.read_session(path)
    data["events"] = [complete_event()]
    data["final_analysis_complete"] = True
    data["stage_log"] += [{"stage": s} for s in ("requirements", "classification", "final_analysis")]
    core.write_session(data, path)


# ---------------------------------------------------------------------------
# A stub MCP SDK: records what the facade registers, so the allowlist is
# testable on a machine without the optional dependency.
# ---------------------------------------------------------------------------
class StubFastMCP:
    def __init__(self, name, instructions=None, **kwargs):
        self.name = name
        self.instructions = instructions or ""
        self.kwargs = kwargs
        self.tools: dict = {}
        self.other_registrations: list[str] = []
        self.ran_with = None

    def tool(self, *args, **kwargs):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register

    def run(self, transport=None):
        self.ran_with = transport

    def __getattr__(self, attr):
        # resource(), prompt(), add_tool(), custom_route()... anything else the
        # facade might call is recorded so the test can refuse it.
        def record(*args, **kwargs):
            self.other_registrations.append(attr)
            return lambda fn=None: fn
        return record


@contextlib.contextmanager
def stub_sdk():
    names = ("mcp", "mcp.server", "mcp.server.fastmcp")
    saved = {n: sys.modules.get(n) for n in names}
    top, server, fast = (types.ModuleType(n) for n in names)
    fast.FastMCP = StubFastMCP
    top.server, server.fastmcp = server, fast
    sys.modules.update(dict(zip(names, (top, server, fast))))
    try:
        yield
    finally:
        for n, mod in saved.items():
            if mod is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = mod


def real_sdk_available() -> bool:
    try:
        from mcp.server.fastmcp import FastMCP  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — the repo's mcp/ folder imports as a namespace package
        return False


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        session = tmp / "session.json"

        print("\nPhase 1 — session lifecycle")
        core.start(session, "high")
        check("new session validates", core.validate(session)[0])
        check("default is high privacy", core.read_session(session)["privacy_tier"] == "high")
        try:
            core.start(session, "high")
            overwrite_blocked = False
        except core.SessionError:
            overwrite_blocked = True
        check("unfinished session is not overwritten", overwrite_blocked)

        answers = ["industry", "holder", "sf-86", "secret", "A fictional OWI happened in June. No classified information is included."]
        for answer in answers:
            core.answer_intake(answer, session)
        data = core.read_session(session)
        check("intake completes one answer at a time", core.next_question(data) is None)
        check("narrative is deterministically stamped", len(data.get("narrative_sha256", "")) == 64)
        check("intake stage is logged", data["stage_log"][-1]["stage"] == "intake")

        data["narrative"] += " changed"
        session.write_text(json.dumps(data), encoding="utf-8")
        check("narrative mutation fails validation", not core.validate(session)[0])

        print("\nPhase 1 — session file edge cases")
        missing = tmp / "nowhere" / "session.json"
        msg = raises(core.read_session, missing)
        check("a missing session is a clear error, not a traceback", msg is not None and "No session exists" in msg, str(msg))
        corrupt = tmp / "corrupt.json"
        corrupt.write_text("{not json", encoding="utf-8")
        msg = raises(core.read_session, corrupt)
        check("a corrupt session file is reported as invalid JSON", msg is not None and "not valid JSON" in msg, str(msg))
        check("status on a missing session raises rather than inventing state", raises(core.status, missing) is not None)

        nested = tmp / "deep" / "er" / "session.json"
        core.write_session({"privacy_tier": "low"}, nested)
        check("write_session creates parent folders", nested.exists())
        check("write_session leaves no temporary file behind",
              not any(p.name.endswith(".tmp") for p in nested.parent.iterdir()),
              str(list(nested.parent.iterdir())))
        check("write_session writes UTF-8 JSON with a trailing newline",
              nested.read_text(encoding="utf-8").endswith("}\n") and json.loads(nested.read_text(encoding="utf-8")) == {"privacy_tier": "low"})

        fresh = tmp / "fresh.json"
        core.start(fresh)
        d = core.read_session(fresh)
        check("a new session has not recorded a privacy choice for the user",
              d["privacy_tier_chosen_by_user"] is False and d["_runner"]["pending_privacy"] is True)
        check("the deployment mode is disclosed from the first checkpoint", d["deployment_mode_disclosed"] is True)
        check("privacy is asked first even though the schema needed a placeholder tier",
              core.next_question(d).key == "privacy_tier")
        d["population"] = "industry"  # an out-of-order key must not skip the privacy question
        check("a pending privacy choice outranks every other question", core.next_question(d).key == "privacy_tier")

        core.answer_intake("low", fresh)
        d = core.read_session(fresh)
        check("an explicit privacy answer is recorded as the user's choice",
              d["privacy_tier"] == "low" and d["privacy_tier_chosen_by_user"] is True and d["_runner"]["pending_privacy"] is False)
        check("low and medium tiers carry no Person-N mapping notice", "mapping_notice_delivered" not in d)
        core.answer_intake("federal", fresh)
        d = core.read_session(fresh)
        check("position type is derived from scope, never asked", d["position_type"] == "national_security")

        hp = tmp / "high.json"
        core.start(hp, "high")
        d = core.read_session(hp)
        check("tier high records the mapping notice and the user's own words",
              d["mapping_notice_delivered"] is True and d["user_confirmations"]["mapping_notice"] == "high")

        intake(fresh)
        check("answering after intake is complete is refused",
              "already complete" in (raises(core.answer_intake, "more", fresh) or ""))

        blank = tmp / "blank.json"
        core.start(blank, "medium")
        for a in INTAKE[:-1]:
            core.answer_intake(a, blank)
        check("a whitespace-only narrative is refused",
              "cannot be empty" in (raises(core.answer_intake, "   \n\t ", blank) or ""))
        check("an unrecognizable answer is refused with examples, never guessed",
              "could not confidently understand" in (raises(core.normalize, "population", "purple") or ""))

        st = core.status(fresh)
        check("status reports a complete intake with no next question",
              st["intake_complete"] is True and st["next_question"] is None and st["narrative_stamped"] is True)
        check("status counts matters and required fields without content",
              st["matters"] == 0 and st["required_remaining"] == 0 and st["last_stage"] == "intake")

        print("\nPhase 1 — assembly and verification through the engine")
        full = tmp / "full" / "session.json"
        complete_session(full)
        check("a completed synthetic session validates", core.validate(full)[0], core.validate(full)[1][-300:])
        pkg, detail = core.assemble(full)
        check("assembly writes the package beside the session by default",
              pkg == full.parent / "package.md" and pkg.exists(), detail)
        digest, detail = core.verify(full)
        check("verification returns the package's real SHA-256",
              digest == hashlib.sha256(pkg.read_bytes()).hexdigest(), detail[-300:])
        check("verification writes the sidecar the user compares against",
              (full.parent / "package.md.sha256").read_text(encoding="utf-8").startswith(digest))
        custom = tmp / "elsewhere" / "report.md"
        out, _ = core.assemble(full, custom)
        check("an explicit output path is honored", out == custom and custom.exists())
        check("an explicit package path is verified", core.verify(full, custom)[0] == hashlib.sha256(custom.read_bytes()).hexdigest())

        tampered = custom.read_text(encoding="utf-8") + "\nYour case should be fine.\n"
        custom.write_text(tampered, encoding="utf-8")
        msg = raises(core.verify, full, custom)
        check("a package edited after assembly fails the hard gate", msg is not None and "DO NOT DELIVER" in msg, str(msg)[-200:])
        check("verify with no package is refused", raises(core.verify, full, tmp / "absent.md") is not None)

        bad = tmp / "bad" / "session.json"
        complete_session(bad)
        d = core.read_session(bad)
        d["events"][0]["reporting"]["reportable"] = "no"
        core.write_session(d, bad)
        msg = raises(core.assemble, bad)
        check("assembly refuses a session the gate rejects", msg is not None and "assembly stopped" in msg, str(msg))
        check("and writes no package", not (bad.parent / "package.md").exists())

        print("\nPhase 2 — safe shared boundary")
        core.start(session, force=True)
        summary = core.status(session)
        check("status omits narrative content", "fictional owi" not in json.dumps(summary).lower() and "narrative" not in summary)
        check("status exposes exactly one next question", summary["next_question"]["key"] == "privacy_tier")
        command = [sys.executable, str(ROOT / "scripts" / "adverse.py"), "--session", str(session), "status"]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        check("repository CLI entry point works", result.returncode == 0 and '"valid": true' in result.stdout.lower(), result.stdout + result.stderr)

        print("\nPhase 2 — command line")
        cs = tmp / "cli" / "session.json"
        r = adverse("--session", str(cs), "start", "--privacy", "medium")
        check("start creates a validated checkpoint", r.returncode == 0 and json.loads(r.stdout)["valid"] is True, r.stdout + r.stderr)
        r = adverse("--session", str(cs), "start")
        check("a second start is refused without --force",
              r.returncode == 1 and "would be overwritten" in r.stderr and r.stdout == "", r.stdout + r.stderr)
        r = adverse("--session", str(cs), "start", "--force")
        check("--force replaces the named session", r.returncode == 0 and json.loads(r.stdout)["next_question"]["key"] == "privacy_tier")
        r = adverse("--session", str(cs), "resume")
        check("resume shows the one next question", r.returncode == 0 and json.loads(r.stdout)["next_question"]["key"] == "privacy_tier")
        r = adverse("--session", str(cs), "answer", "medium")
        check("answer records one fact and reports progress",
              r.returncode == 0 and json.loads(r.stdout)["next_question"]["key"] == "population", r.stdout + r.stderr)
        r = adverse("--session", str(cs), "answer", "purple")
        check("an unrecognized answer exits 1 with the reason on stderr",
              r.returncode == 1 and "could not confidently understand" in r.stderr, r.stdout + r.stderr)
        r = adverse("--session", str(cs), "validate")
        check("validate exits 0 on a sound session", r.returncode == 0 and "PASS" in r.stdout, r.stdout + r.stderr)
        d = core.read_session(cs)
        d["privacy_tier"] = "maximum"
        core.write_session(d, cs)
        r = adverse("--session", str(cs), "validate")
        check("validate exits 1 on an unsound session", r.returncode == 1 and "FAIL" in r.stdout, r.stdout + r.stderr)
        r = adverse("--session", str(tmp / "none.json"), "status")
        check("status on a missing session exits 1 without a traceback",
              r.returncode == 1 and "No session exists" in r.stderr and "Traceback" not in r.stderr, r.stderr)

        fs = tmp / "clifull" / "session.json"
        complete_session(fs)
        out_pkg = tmp / "clifull" / "out" / "pkg.md"
        r = adverse("--session", str(fs), "assemble", "--output", str(out_pkg))
        check("assemble --output writes the package and reports its path",
              r.returncode == 0 and Path(json.loads(r.stdout)["package"]) == out_pkg.resolve(), r.stdout + r.stderr)
        r = adverse("--session", str(fs), "verify", "--package", str(out_pkg))
        check("verify --package returns the package SHA-256",
              r.returncode == 0 and json.loads(r.stdout)["sha256"] == hashlib.sha256(out_pkg.read_bytes()).hexdigest(), r.stdout + r.stderr)
        r = adverse("--session", str(fs), "verify", "--package", str(tmp / "missing.md"))
        check("verify on a missing package exits 1", r.returncode == 1, r.stdout + r.stderr)

        code, _, err = cli_main()
        check("no command is a usage error", code == 2 and "required" in err.lower(), err)
        code, _, err = cli_main("--session", str(cs), "start", "--privacy", "maximum")
        check("start --privacy only accepts the three tiers", code == 2, err)
        r = subprocess.run([sys.executable, "-m", "adverse_app", "--session", str(fs), "status"], cwd=ROOT,
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
        check("python -m adverse_app runs the same CLI",
              r.returncode == 0 and json.loads(r.stdout)["intake_complete"] is True, r.stdout + r.stderr)

        print("\nPhase 2 — local MCP facade: a narrow allowlist")
        ms = tmp / "mcp" / "session.json"
        with stub_sdk():
            from adverse_app import mcp_server
            server = mcp_server.create_server(ms)
            check("the facade exposes exactly the six documented tools",
                  set(server.tools) == LOCAL_MCP_TOOLS, str(sorted(server.tools)))
            check("it registers no resources, prompts or other routes", server.other_registrations == [],
                  str(server.other_registrations))
            params = {name: list(inspect.signature(fn).parameters) for name, fn in server.tools.items()}
            check("only answer_intake_question takes an argument, and it is the answer text",
                  params.pop("answer_intake_question") == ["answer"] and all(not p for p in params.values()), str(params))
            check("no tool accepts a path, so no tool reaches beyond the bound session",
                  not any(p for fn in server.tools.values() for p in inspect.signature(fn).parameters
                          if any(w in p.lower() for w in ("path", "file", "dir", "session", "package", "output"))))
            check("the server's instructions carry the never-collect floor",
                  all(w in server.instructions for w in ("classified", "SSN", "dates of birth", "real name")))

            core.start(ms)
            check("next_intake_question returns only the approved question",
                  server.tools["next_intake_question"]() == {"complete": False, "key": "privacy_tier", "prompt": core.QUESTIONS[0].prompt})
            st = server.tools["answer_intake_question"]("medium")
            check("answer_intake_question saves to the bound session and returns compact progress",
                  st["next_question"]["key"] == "population" and core.read_session(ms)["privacy_tier"] == "medium")
            for a in INTAKE:
                server.tools["answer_intake_question"](a)
            st = server.tools["session_status"]()
            check("session_status never returns narrative text",
                  "fictional owi" not in json.dumps(st).lower() and st["narrative_stamped"] is True)
            check("next_intake_question reports completion", server.tools["next_intake_question"]()["complete"] is True)
            check("validate_session reports the gate result", server.tools["validate_session"]()["valid"] is True)

            d = core.read_session(ms)
            d["events"] = [complete_event()]
            d["final_analysis_complete"] = True
            core.write_session(d, ms)
            res = server.tools["assemble_package"]()
            check("assemble_package writes only beside the bound session",
                  Path(res["package"]) == (ms.parent / "package.md").resolve())
            res = server.tools["verify_package"]()
            check("verify_package returns the hash of that package",
                  res["sha256"] == hashlib.sha256((ms.parent / "package.md").read_bytes()).hexdigest())

            code, _, err = cli_main("--session", str(ms), "mcp")
            check("the mcp command serves over stdio only, never a network port", code == 0, err)
        if real_sdk_available():
            import asyncio
            from adverse_app import mcp_server as real_facade
            real = real_facade.create_server(ms)
            names = {t.name for t in asyncio.run(real.list_tools())}
            check("with the real SDK, list_tools is the same six", names == LOCAL_MCP_TOOLS, str(sorted(names)))
            check("with the real SDK, no resources are listed", asyncio.run(real.list_resources()) == [])
        else:
            print("  SKIP  real MCP SDK not installed; the allowlist was checked through the stub")
            r = adverse("--session", str(ms), "mcp")
            check("without the SDK, mcp exits 1 with a clear message rather than a traceback",
                  r.returncode == 1 and "MCP SDK is not installed" in r.stderr and "Traceback" not in r.stderr, r.stderr)

        design = (ROOT / "docs" / "HOSTED-MCP-DESIGN.md").read_text(encoding="utf-8")
        check("the design document names the same six local tools",
              all(f"`{t}`" in design for t in LOCAL_MCP_TOOLS) and "has six tools" in design)

        print("\nPhase 2 — tolerant intake language")
        check("basic population typo is accepted", core.normalize("population", "indstry") == "industry")
        check("ordinary population prose is accepted", core.normalize("population", "I work for a defense contractor") == "industry")
        check("basic role typo is accepted", core.normalize("role", "hoder") == "holder")
        check("form punctuation variation is accepted", core.normalize("form", "I am completing the SF 86") == "sf86")
        check("privacy typo is accepted", core.normalize("privacy_tier", "medum") == "medium")
        check("access prose is accepted", core.normalize("access_tier", "I have a Q clearance") == "ts_q")
        check("access question uses user-facing terms", core.QUESTIONS[4].prompt == "Is your access Secret, Top Secret, Q, or not applicable?")
        check("the longest matching phrase wins over a shorter one inside it",
              core.normalize("access_tier", "I hold Secret, not Top Secret") == "baseline")
        check("case and spacing do not matter", core.normalize("form", "  PVQ  ") == "pvq")

        print("\nPhase 2 — intake language never lowers the access tier")
        # A Top Secret holder read as Secret is pointed at the wrong reporting
        # table: the TS/Q requirements simply never come up.
        for said in ("Top-Secret", "TOP SECRET.", "Top Secret/SCI", "TS/SCI", "TS-SCI", "topsecret", "Q."):
            got = core.normalize("access_tier", said)
            check(f"access {said!r} is Top Secret/Q", got == "ts_q", got)
        for said in ("Secret.", "Secret, interim", "confidential"):
            got = core.normalize("access_tier", said)
            check(f"access {said!r} is Secret", got == "baseline", got)
        # A phrase must be a whole word: the "ts" inside "results" is not TS.
        check("a word that merely contains 'ts' is not Top Secret",
              raises(core.normalize, "access_tier", "No clearance yet, I am still waiting on my results") is not None)
        check("'none' inside 'someone' is not 'not applicable'",
              raises(core.normalize, "access_tier", "someone else handles that") is not None)
        check("a whole-word 'none' still means not applicable",
              core.normalize("access_tier", "None, my parents say I need one") == "not_applicable")
        check("SF-86 with punctuation inside a sentence is still the SF-86",
              core.normalize("form", "the SF-86 form") == "sf86")

        print("\nPhase 2 — the three-way status route")
        # intake.md §5: applicant, in_process and holder are three routes, and
        # in_process notifies the sponsoring office rather than preparing a
        # form. Folding it into applicant sends the package the wrong way.
        for said in ("in process", "in_process", "In-process", "I'm in process for a clearance",
                     "I applied and my investigation is pending", "awaiting adjudication"):
            got = core.normalize("role", said)
            check(f"role {said!r} is in_process", got == "in_process", got)
        for said in ("applicant", "I am applying", "I haven't submitted my SF-86 yet", "not yet submitted"):
            got = core.normalize("role", said)
            check(f"role {said!r} is applicant", got == "applicant", got)
        check("a holder is still a holder", core.normalize("role", "I already hold a clearance") == "holder")
        check("the role question names all three routes",
              all(w in core.QUESTIONS[2].prompt for w in ("holder", "in process", "applicant")))
        ip = tmp / "inprocess.json"
        core.start(ip, "medium")
        for a in ("industry", "in process", "sf-86", "secret", "A fictional matter happened."):
            core.answer_intake(a, ip)
        check("an in-process intake records in_process and validates",
              core.read_session(ip)["role"] == "in_process" and core.validate(ip)[0])

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
