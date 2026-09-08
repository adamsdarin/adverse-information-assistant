#!/usr/bin/env python3
"""End-to-end tests for the Phase 1–2 product shell."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adverse_app import core

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


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        session = Path(td) / "session.json"
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

        print("\nPhase 2 — safe shared boundary")
        core.start(session, force=True)
        summary = core.status(session)
        check("status omits narrative content", "fictional owi" not in json.dumps(summary).lower() and "narrative" not in summary)
        check("status exposes exactly one next question", summary["next_question"]["key"] == "privacy_tier")
        command = [sys.executable, str(ROOT / "scripts" / "adverse.py"), "--session", str(session), "status"]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        check("repository CLI entry point works", result.returncode == 0 and '"valid": true' in result.stdout.lower(), result.stdout + result.stderr)

        print("\nPhase 2 — tolerant intake language")
        check("basic population typo is accepted", core.normalize("population", "indstry") == "industry")
        check("ordinary population prose is accepted", core.normalize("population", "I work for a defense contractor") == "industry")
        check("basic role typo is accepted", core.normalize("role", "hoder") == "holder")
        check("form punctuation variation is accepted", core.normalize("form", "I am completing the SF 86") == "sf86")
        check("privacy typo is accepted", core.normalize("privacy_tier", "medum") == "medium")
        check("access prose is accepted", core.normalize("access_tier", "I have a Q clearance") == "ts_q")
        check("access question uses user-facing terms", core.QUESTIONS[4].prompt == "Is your access Secret, Top Secret, Q, or not applicable?")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
