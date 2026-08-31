"""Shared session engine used by the CLI, browser, and MCP adapter.

The engine deliberately owns only deterministic product concerns. Specialist
reasoning remains with the host model following agents/conductor.md.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from difflib import get_close_matches
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSION = ROOT / "output" / "session.json"


@dataclass(frozen=True)
class IntakeQuestion:
    key: str
    prompt: str


QUESTIONS = (
    IntakeQuestion("privacy_tier", "Choose high, medium, or low privacy for information about other people. High uses Person-N placeholders, and you must keep the identity mapping separately off this system."),
    IntakeQuestion("population", "Are you in cleared industry, or are you a federal or military user?"),
    IntakeQuestion("role", "Are you currently a clearance holder or an applicant?"),
    IntakeQuestion("form", "Are you preparing for the SF-86, the PVQ, or an incident report?"),
    IntakeQuestion("access_tier", "Is your access Secret, Top Secret, Q, or not applicable?"),
    IntakeQuestion("narrative", "In your own words, what happened? Do not include classified information, Social Security numbers, or dates of birth."),
)

NORMALIZE = {
    "population": {"contractor": "industry", "industry": "industry", "federal": "federal", "military": "federal"},
    "role": {"holder": "holder", "applicant": "applicant"},
    "form": {"sf86": "sf86", "sf-86": "sf86", "pvq": "pvq", "incident": "incident_report", "incident report": "incident_report"},
    "access_tier": {"baseline": "baseline", "secret": "baseline", "ts": "ts_q", "top secret": "ts_q", "q": "ts_q", "not applicable": "not_applicable", "n/a": "not_applicable"},
    "privacy_tier": {"high": "high", "medium": "medium", "low": "low"},
}

PHRASE_ALIASES = {
    "population": {
        "industry": ("contractor", "cleared industry", "private company", "defense contractor"),
        "federal": ("federal employee", "government employee", "civilian employee", "military", "service member"),
    },
    "role": {
        "holder": ("clearance holder", "currently cleared", "i have a clearance", "already hold"),
        "applicant": ("clearance applicant", "applying", "in process", "candidate"),
    },
    "form": {
        "sf86": ("sf 86", "standard form 86", "eapp"),
        "pvq": ("personnel vetting questionnaire",),
        "incident_report": ("incident report", "self report", "adverse report"),
    },
    "access_tier": {
        "baseline": ("secret", "confidential", "not top secret"),
        "ts_q": ("top secret", "ts", "q clearance", "q access"),
        "not_applicable": ("not applicable", "none", "unsure"),
    },
    "privacy_tier": {
        "high": ("highest", "most private", "person placeholders"),
        "medium": ("middle", "names only"),
        "low": ("lowest", "full contact details"),
    },
}


class SessionError(RuntimeError):
    pass


def read_session(path: Path = DEFAULT_SESSION) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SessionError(f"No session exists at {path}. Start one first.") from exc
    except json.JSONDecodeError as exc:
        raise SessionError(f"The session file is not valid JSON: {exc}") from exc


def write_session(data: dict[str, Any], path: Path = DEFAULT_SESSION) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_script(name: str, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args],
        cwd=ROOT, capture_output=True, text=True,
    )
    return result.returncode, result.stdout + result.stderr


def validate(path: Path = DEFAULT_SESSION, stamp_narrative: bool = False) -> tuple[bool, str]:
    args = [str(path)]
    if stamp_narrative:
        args.append("--stamp-narrative")
    code, output = run_script("validate_session.py", *args)
    return code == 0, output.strip()


def start(path: Path = DEFAULT_SESSION, privacy_tier: str | None = None, force: bool = False) -> dict[str, Any]:
    if path.exists() and not force:
        raise SessionError(f"An existing session would be overwritten at {path}. Resume it or explicitly use --force.")
    data: dict[str, Any] = {
        # The schema requires a tier before the user has answered. Medium is a
        # non-collecting initialization value and is never represented as the
        # user's choice; _runner.pending_privacy keeps the question active.
        "privacy_tier": "medium",
        "privacy_tier_chosen_by_user": False,
        "deployment_mode_disclosed": True,
        "stage_log": [],
        "events": [],
        "outstanding_required": [],
        "_runner": {"version": 1, "intake_complete": False, "pending_privacy": True},
    }
    write_session(data, path)
    ok, detail = validate(path)
    if not ok:
        raise SessionError(detail)
    if privacy_tier is not None:
        return answer_intake(privacy_tier, path)
    return read_session(path)


def normalize(key: str, answer: str) -> str:
    value = " ".join(answer.strip().lower().split())
    if key == "narrative":
        if not answer.strip():
            raise SessionError("The narrative cannot be empty.")
        return answer.strip()
    mapping = NORMALIZE.get(key, {})
    if value not in mapping:
        phrases: list[tuple[str, str]] = []
        for canonical, aliases in PHRASE_ALIASES.get(key, {}).items():
            phrases.extend((alias, canonical) for alias in aliases)
        for alias, canonical in sorted(phrases, key=lambda item: len(item[0]), reverse=True):
            if alias in value:
                return canonical

        candidates = {**mapping}
        for alias, canonical in phrases:
            candidates[alias] = canonical
        close = get_close_matches(value, candidates.keys(), n=1, cutoff=0.72)
        if close:
            return candidates[close[0]]
        examples = ", ".join(sorted(set(mapping.values())))
        raise SessionError(f"I could not confidently understand that answer for {key}. Please say it another way; examples are: {examples}.")
    return mapping[value]


def next_question(data: dict[str, Any]) -> IntakeQuestion | None:
    if data.get("_runner", {}).get("pending_privacy"):
        return QUESTIONS[0]
    for question in QUESTIONS:
        if question.key not in data:
            return question
    return None


def answer_intake(answer: str, path: Path = DEFAULT_SESSION) -> dict[str, Any]:
    data = read_session(path)
    question = next_question(data)
    if question is None:
        raise SessionError("Intake is already complete.")
    data[question.key] = normalize(question.key, answer)
    if question.key == "privacy_tier":
        data["privacy_tier_chosen_by_user"] = True
        data.setdefault("_runner", {})["pending_privacy"] = False
        if data["privacy_tier"] == "high":
            data["mapping_notice_delivered"] = True
            data.setdefault("user_confirmations", {})["mapping_notice"] = answer.strip()
    if question.key == "population":
        data["position_type"] = "national_security"
    if question.key == "narrative":
        data.setdefault("stage_log", []).append({"stage": "intake", "note": "Narrative captured and stamped by the local runner."})
        data.setdefault("_runner", {})["intake_complete"] = True
    write_session(data, path)
    ok, detail = validate(path, stamp_narrative=question.key == "narrative")
    if not ok:
        raise SessionError(detail)
    return read_session(path)


def status(path: Path = DEFAULT_SESSION) -> dict[str, Any]:
    data = read_session(path)
    question = next_question(data)
    events = data.get("events", [])
    required = data.get("outstanding_required", [])
    stages = data.get("stage_log", [])
    return {
        "session": str(path.resolve()),
        "valid": validate(path)[0],
        "intake_complete": question is None,
        "next_question": None if question is None else {"key": question.key, "prompt": question.prompt},
        "matters": len(events),
        "required_remaining": len(required),
        "last_stage": stages[-1]["stage"] if stages else None,
        "narrative_stamped": bool(data.get("narrative_sha256")),
    }


def assemble(path: Path = DEFAULT_SESSION, output: Path | None = None) -> tuple[Path, str]:
    output = output or path.parent / "package.md"
    ok, detail = validate(path)
    if not ok:
        raise SessionError(f"Session validation failed; assembly stopped.\n{detail}")
    code, detail = run_script("assemble_package.py", str(path), "-o", str(output))
    if code:
        raise SessionError(detail)
    return output, detail.strip()


def verify(path: Path = DEFAULT_SESSION, package: Path | None = None) -> tuple[str, str]:
    package = package or path.parent / "package.md"
    code, detail = run_script("verify_output.py", str(package), str(path))
    if code:
        raise SessionError(detail)
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    return digest, detail.strip()
