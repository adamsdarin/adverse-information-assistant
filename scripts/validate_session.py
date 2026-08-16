#!/usr/bin/env python3
"""Gate the session state file. Part of the trust anchor.

The verifier's other checks consume session.json — a file the model writes.
This script makes that file itself a gated artifact: structure, enums, and
two deterministic anti-tamper properties are checked by code, not by prompt.

What it enforces:
  - Types and enums for every known field (schemas/session.schema.json is the
    reference document; this script is the executable check — stdlib only, no
    dependency on a schema library).
  - `reportable` may be "yes" or "consult_fso", NEVER "no". The tool has no
    authority to determine that a matter is unreportable; a session file
    asserting one is a defect regardless of which model wrote it.
  - Narrative integrity: `--stamp-narrative` computes and records the SHA-256
    of the verbatim intake narrative (deterministic code sets the field, not
    the model). Validation recomputes it; a mismatch means the candor
    baseline was altered after capture, and that is a hard failure.
  - Stage log sanity: only known stage names, append-only.

What it cannot enforce, stated rather than hidden: it cannot prove the
narrative was really what the user typed, or that a confirmation string was
really uttered. It makes silent drift detectable; it does not make lying
impossible.

Usage:
  python scripts/validate_session.py session.json
  python scripts/validate_session.py session.json --stamp-narrative
Exit 0 = valid, 1 = invalid.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

TIERS = {"high", "medium", "low"}
POPULATIONS = {"industry", "federal"}
ROLES = {"applicant", "holder"}
FORMS = {"sf86", "pvq", "incident_report"}
ACCESS_TIERS = {"baseline", "ts_q", "not_applicable"}
POSITION_TYPES = {"national_security", "public_trust", "low_risk"}
GUIDELINES = set("ABCDEFGHIJKLM")
REPORTABLE = {"yes", "consult_fso"}  # "no" is deliberately absent — see docstring
KNOWN_STAGES = {
    "corpus_located", "intake", "requirements", "classification",
    "question_sourcing", "gap_loop", "thread_detection", "consistency",
    "documents", "narrative", "candor", "triage_checkpoint",
    "assembly", "verification", "handoff",
}


def narrative_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate(session: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    def enum(field: str, allowed: set, required: bool = False) -> None:
        v = session.get(field)
        if v is None:
            if required:
                errors.append(f"missing required field '{field}'")
            return
        if v not in allowed:
            errors.append(f"'{field}' is {v!r}; must be one of {sorted(allowed)}")

    enum("privacy_tier", TIERS, required=True)
    enum("population", POPULATIONS)
    enum("role", ROLES)
    enum("form", FORMS)
    enum("access_tier", ACCESS_TIERS)
    enum("position_type", POSITION_TYPES)

    if session.get("privacy_tier") == "high":
        if not session.get("mapping_notice_delivered"):
            errors.append(
                "privacy_tier is 'high' but mapping_notice_delivered is not true — "
                "the user is the only record of who Person N is"
            )
        if not str(session.get("user_confirmations", {}).get("mapping_notice", "")).strip():
            warnings.append(
                "mapping_notice_delivered is set but user_confirmations.mapping_notice "
                "holds no confirmation text — the flag rests on the model's word alone"
            )

    # --- narrative integrity -------------------------------------------------
    narrative = session.get("narrative")
    stamp = session.get("narrative_sha256")
    if narrative is not None and not isinstance(narrative, str):
        errors.append("'narrative' must be a string (the user's verbatim account)")
    if stamp:
        if narrative is None:
            errors.append("narrative_sha256 present but 'narrative' is missing")
        elif narrative_hash(narrative) != stamp:
            errors.append(
                "NARRATIVE ALTERED AFTER CAPTURE: narrative_sha256 does not match "
                "the current 'narrative' text. The verbatim intake account is the "
                "baseline for the candor check; it must never be rewritten."
            )
    elif narrative is not None:
        warnings.append(
            "narrative is present but unstamped — run "
            "'validate_session.py session.json --stamp-narrative' right after capture"
        )

    # --- events --------------------------------------------------------------
    events = session.get("events", [])
    if not isinstance(events, list):
        errors.append("'events' must be a list")
        events = []
    for i, ev in enumerate(events):
        where = f"events[{i}]"
        if not isinstance(ev, dict):
            errors.append(f"{where}: must be an object")
            continue
        for g in ev.get("guidelines", []):
            if g not in GUIDELINES:
                errors.append(f"{where}: invalid guideline {g!r}")
        rep = ev.get("reporting") or {}
        r = rep.get("reportable")
        if r is not None and r not in REPORTABLE:
            if r == "no":
                errors.append(
                    f"{where}: reporting.reportable is 'no'. This tool never "
                    "determines that a matter is unreportable — only 'yes' or "
                    "'consult_fso'. A 'no' here is discouraging a report."
                )
            else:
                errors.append(f"{where}: reporting.reportable is {r!r}; "
                              f"must be one of {sorted(REPORTABLE)}")
        for p in ev.get("persons", []):
            if not isinstance(p, dict) or not p.get("label"):
                errors.append(f"{where}: every persons[] entry needs a 'label'")

    # --- outstanding required ------------------------------------------------
    for i, item in enumerate(session.get("outstanding_required", [])):
        if not isinstance(item, dict) or not item.get("element"):
            errors.append(f"outstanding_required[{i}]: needs an 'element'")

    # --- stage log -----------------------------------------------------------
    log = session.get("stage_log", [])
    if not isinstance(log, list):
        errors.append("'stage_log' must be a list")
        log = []
    for i, entry in enumerate(log):
        if not isinstance(entry, dict) or entry.get("stage") not in KNOWN_STAGES:
            errors.append(
                f"stage_log[{i}]: unknown or missing stage "
                f"(known: {sorted(KNOWN_STAGES)})"
            )
    prev = session.get("stage_log_length_at_last_validate")
    if isinstance(prev, int) and len(log) < prev:
        errors.append(
            f"stage_log SHRANK ({prev} -> {len(log)}). The log is append-only; "
            "entries must never be removed or rewritten."
        )

    return errors, warnings


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("usage: validate_session.py <session.json> [--stamp-narrative]")
        return 1
    path = Path(args[0])
    if not path.exists():
        print(f"ERROR: {path} not found")
        return 1
    try:
        session = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL  session file is not valid JSON: {e}")
        return 1

    if "--stamp-narrative" in sys.argv:
        narrative = session.get("narrative")
        if not isinstance(narrative, str) or not narrative.strip():
            print("FAIL  cannot stamp: 'narrative' is missing or empty")
            return 1
        session["narrative_sha256"] = narrative_hash(narrative)
        path.write_text(json.dumps(session, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"Stamped narrative_sha256 = {session['narrative_sha256']}")
        # fall through and validate the stamped file

    errors, warnings = validate(session)

    # Record the log length so the next validation can detect shrinkage.
    if not errors and isinstance(session.get("stage_log"), list):
        session["stage_log_length_at_last_validate"] = len(session["stage_log"])
        path.write_text(json.dumps(session, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"FAIL  {e}")
    if errors:
        print(f"\n{len(errors)} failure(s). The session file is not trustworthy; "
              "fix it before assembling or verifying a package.")
        return 1
    print("PASS  session file is structurally sound.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
