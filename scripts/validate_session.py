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
import re
import sys
from pathlib import Path

# Namespaced reportable-event id, e.g. aci.travel.unofficial, adv.crypto.foreign,
# tsq.finance.anomalies. Format only — existence is validate_corpus.py's job.
EVENT_ID_RE = re.compile(r"^[a-z]+(?:\.[a-z0-9-]+)+$")

TIERS = {"high", "medium", "low"}
POPULATIONS = {"industry", "federal"}
ROLES = {"applicant", "in_process", "holder"}
FORMS = {"sf86", "pvq", "incident_report"}
ACCESS_TIERS = {"baseline", "ts_q", "not_applicable"}
# Only one value is valid. Everyone this tool serves holds, or is in process
# for, eligibility for access to classified information — a national security
# position by definition. Public trust and low-risk positions do not carry
# clearances. This is not a preference: the wrong value silently swaps which
# PVQ Parts the crosswalk cites, so the package would point a user at form
# sections that are not theirs.
POSITION_TYPES = {"national_security"}
GUIDELINES = set("ABCDEFGHIJKLM")
REPORTABLE = {"yes", "consult_fso"}  # "no" is deliberately absent — see docstring
FIELD_STATUSES = {"pending", "not_applicable", "unknown"}
DISS_INCIDENT_TYPES = {
    "Allegiance to the United States", "Foreign Influence", "Foreign Preference",
    "Sexual Behavior", "Use of Information Technology", "Personal Conduct",
    "Financial Considerations", "Alcohol Consumption", "Psychological Conditions",
    "Drug Involvement and Substance Misuse", "Criminal Conduct",
    "Handling Protected Information", "Outside Activities", "Continuous Evaluations",
}
INCIDENT_DEVELOPMENT_PHASES = {
    "before", "precipitating_circumstances", "decisions_and_actions",
    "incident", "immediate_aftermath", "later_consequences",
    "current_status", "future_developments",
}
INCIDENT_DEVELOPMENT_STATUSES = {
    "answered", "unknown", "not_applicable", "declined",
}
INCIDENT_DEVELOPMENT_PROFILES = {
    "general-incident", "impaired-driving", "violent-conduct",
    "domestic-or-intimate-partner-violence", "arrest-or-criminal-process",
    "foreign-contact-or-influence", "financial-event",
    "substance-use-or-treatment", "information-or-technology",
}
NON_DATE_ANSWERS = re.compile(
    r"^(?:n/?a|not applicable|none|unknown|not (?:yet )?(?:known|obtained|resolved)|pending)\b",
    re.IGNORECASE,
)
PRIOR_DISCLOSURE = {"not_asked", "disclosed_unchanged", "disclosed_but_changed",
                    "not_disclosed", "uncertain"}
KNOWN_STAGES = {
    "corpus_located", "intake", "requirements", "classification",
    "question_sourcing", "gap_loop", "thread_detection", "consistency",
    "documents", "narrative", "candor", "triage_checkpoint",
    "final_analysis", "assembly", "verification", "handoff",
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
    if session.get("position_type") is not None and \
            session["position_type"] not in POSITION_TYPES:
        errors.append(
            f"position_type is {session['position_type']!r}. This tool serves "
            "clearance holders and applicants only, so the sole valid value is "
            "'national_security' — it is derived from scope, never asked. A "
            "different value means either the session is out of scope (see the "
            "intake scope check) or the value was asked for and mis-set; either "
            "way the form crosswalk would cite the wrong PVQ Parts."
        )
    if session.get("out_of_scope_acknowledged"):
        for i, ev in enumerate(session.get("events", []) or []):
            if isinstance(ev, dict) and (ev.get("reporting") or {}).get("reportable"):
                errors.append(
                    f"events[{i}]: the user was flagged as outside this tool's "
                    "scope, so no reportability determination may be produced "
                    "for them — those rules are not theirs."
                )

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
    role = session.get("role")
    final_complete = session.get("final_analysis_complete") is True
    if events and role is None:
        errors.append("events are present but 'role' is missing; route must be applicant, in_process, or holder")
    if final_complete and not events:
        errors.append("final_analysis_complete is true but no incidents exist")
    for i, ev in enumerate(events):
        where = f"events[{i}]"
        if not isinstance(ev, dict):
            errors.append(f"{where}: must be an object")
            continue
        for g in ev.get("guidelines", []):
            if g not in GUIDELINES:
                errors.append(f"{where}: invalid guideline {g!r}")
        incident_types = ev.get("incident_types", []) or []
        if not isinstance(incident_types, list):
            errors.append(f"{where}: incident_types must be a list")
            incident_types = []
        for incident_type in incident_types:
            if incident_type not in DISS_INCIDENT_TYPES:
                errors.append(f"{where}: unknown DISS incident type {incident_type!r}")
        if final_complete and role == "holder" and not incident_types:
            errors.append(f"{where}: a holder's completed incident needs at least one DISS incident type")
        if role in {"applicant", "in_process"} and incident_types:
            errors.append(f"{where}: {role} output uses form crosswalks, not DISS incident types")
        development = ev.get("incident_development")
        if final_complete:
            if not isinstance(development, dict):
                errors.append(
                    f"{where}: final analysis cannot complete before "
                    "incident_development is present and gated"
                )
            else:
                profiles = development.get("profiles")
                if not isinstance(profiles, list) or not profiles or any(
                        not isinstance(p, str) or not p.strip() for p in profiles):
                    errors.append(f"{where}: incident_development.profiles must be a non-empty list")
                elif unknown_profiles := set(profiles) - INCIDENT_DEVELOPMENT_PROFILES:
                    errors.append(
                        f"{where}: unknown incident-development profiles: "
                        f"{', '.join(sorted(unknown_profiles))}"
                    )
                phases = development.get("phases")
                if not isinstance(phases, dict):
                    errors.append(f"{where}: incident_development.phases must be an object")
                    phases = {}
                missing_phases = INCIDENT_DEVELOPMENT_PHASES - set(phases)
                if missing_phases:
                    errors.append(
                        f"{where}: incident_development is missing phases: "
                        f"{', '.join(sorted(missing_phases))}"
                    )
                outstanding_names = {
                    str(item.get("element", ""))
                    for item in session.get("outstanding_required", []) or []
                    if isinstance(item, dict)
                }
                declined_names = set(ev.get("declined_elements", []) or [])
                for phase in sorted(INCIDENT_DEVELOPMENT_PHASES & set(phases)):
                    record = phases[phase]
                    if not isinstance(record, dict):
                        errors.append(f"{where}: incident_development.{phase} must be an object")
                        continue
                    status = record.get("status")
                    evidence = record.get("evidence")
                    if status not in INCIDENT_DEVELOPMENT_STATUSES:
                        errors.append(
                            f"{where}: incident_development.{phase}.status must be one of "
                            f"{sorted(INCIDENT_DEVELOPMENT_STATUSES)}"
                        )
                    if not isinstance(evidence, str) or not evidence.strip():
                        errors.append(f"{where}: incident_development.{phase}.evidence is required")
                    key = f"incident_development.{phase}"
                    if status == "unknown" and key not in outstanding_names:
                        errors.append(f"{where}: unknown {key} must be listed in outstanding_required")
                    if status == "declined" and key not in declined_names:
                        errors.append(f"{where}: declined {key} must be listed in declined_elements")
                    if status == "not_applicable" and str(evidence).strip().lower() in {
                            "n/a", "na", "not applicable"}:
                        errors.append(f"{where}: {key} needs a concrete reason for not_applicable")
                if development.get("complete") is not True:
                    errors.append(f"{where}: incident_development.complete must be true before final analysis")
        update_topics = ev.get("future_update_topics", []) or []
        if not isinstance(update_topics, list) or any(
                not isinstance(topic, str) or not topic.strip() for topic in update_topics):
            errors.append(f"{where}: future_update_topics must be a list of non-empty strings")
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
        # `basis` carries the matched table entry ids, and those ids do two
        # jobs: they cite the obligation and they select the event checklist
        # that supplies the questions. A malformed id selects nothing, so the
        # matter reaches the gap analyst with a reportability answer and no
        # questions behind it — and nothing downstream notices.
        #
        # WHAT THIS CHECK CANNOT DO, stated rather than hidden: this script is
        # stdlib-only and does not read the corpus, so it cannot tell whether
        # an id exists. validate_corpus.py owns existence. And `basis` may
        # legitimately hold a non-id citation (a form question, say), so only
        # entries that look namespaced are held to the id grammar. A confident
        # invention like "aci.travel.foreign" passes here and fails there.
        basis = rep.get("basis")
        if basis is not None:
            if not isinstance(basis, list):
                errors.append(f"{where}: reporting.basis must be a list")
            else:
                for b in basis:
                    if not isinstance(b, str) or not b.strip():
                        errors.append(f"{where}: reporting.basis entry {b!r} is not a "
                                      "non-empty string")
                    elif "." in b and not EVENT_ID_RE.match(b):
                        errors.append(
                            f"{where}: reporting.basis entry {b!r} looks like a "
                            "reportable-event id but is malformed — it would select "
                            "no event checklist (expected e.g. 'aci.travel.unofficial')"
                        )
        pd = ev.get("prior_disclosure")
        if pd is not None:
            if not isinstance(pd, dict) or pd.get("status") not in PRIOR_DISCLOSURE:
                errors.append(f"{where}: prior_disclosure.status must be one of "
                              f"{sorted(PRIOR_DISCLOSURE)}")
            else:
                st = pd["status"]
                # A matter the user says is already in their file must not be
                # turned into a fresh reporting instruction — that is the
                # rehashing this check exists to prevent.
                if st == "disclosed_unchanged":
                    if r == "yes":
                        errors.append(
                            f"{where}: prior_disclosure is 'disclosed_unchanged' but "
                            "reportable is 'yes'. On the user's account this is not "
                            "new information; asserting a fresh obligation sends them "
                            "to re-report what the government already has."
                        )
                    if not rep.get("no_new_obligation_identified"):
                        errors.append(
                            f"{where}: prior_disclosure is 'disclosed_unchanged' but "
                            "reporting.no_new_obligation_identified is not set — the "
                            "relief given to the user is not recorded anywhere"
                        )
                    if not str(pd.get("user_statement", "")).strip():
                        errors.append(
                            f"{where}: 'disclosed_unchanged' rests entirely on the "
                            "user's account, so prior_disclosure.user_statement must "
                            "record what they actually said"
                        )
                if st == "disclosed_but_changed" and not str(pd.get("what_changed") or "").strip():
                    errors.append(
                        f"{where}: prior_disclosure is 'disclosed_but_changed' but "
                        "what_changed is empty. The CHANGE is the reportable matter; "
                        "without it there is nothing to assess."
                    )
                if rep.get("no_new_obligation_identified") and st != "disclosed_unchanged":
                    errors.append(
                        f"{where}: no_new_obligation_identified is set but "
                        f"prior_disclosure.status is {st!r}. That relief is only "
                        "available on a stated, unchanged prior disclosure."
                    )
        elif rep.get("no_new_obligation_identified"):
            errors.append(
                f"{where}: no_new_obligation_identified is set with no "
                "prior_disclosure record to support it"
            )

        # Crosswalk date fields feed date-shaped controls in eApp/PVQ. A model
        # must not put a case status ("pending", "not yet resolved", etc.) in
        # one merely because no date exists. Record that condition separately;
        # the renderer can then explain it without inventing a date value.
        for j, crosswalk in enumerate(ev.get("crosswalk", []) or []):
            if not isinstance(crosswalk, dict):
                errors.append(f"{where}.crosswalk[{j}]: must be an object")
                continue
            for k, field in enumerate(crosswalk.get("fields", []) or []):
                if not isinstance(field, dict):
                    continue
                field_where = f"{where}.crosswalk[{j}].fields[{k}]"
                status = field.get("status")
                if status is not None and status not in FIELD_STATUSES:
                    errors.append(
                        f"{field_where}: status is {status!r}; must be one of "
                        f"{sorted(FIELD_STATUSES)}"
                    )
                field_id = str(field.get("id", ""))
                answer = field.get("answer")
                is_date = field_id.endswith("_date") or field_id.endswith("_dates")
                if is_date and isinstance(answer, str) and NON_DATE_ANSWERS.match(answer.strip()):
                    errors.append(
                        f"{field_where}: {field_id!r} is a date field but its answer "
                        f"is a status ({answer!r}). Omit 'answer' and set status to "
                        "'pending', 'not_applicable', or 'unknown' instead."
                    )
                if is_date and status is not None and answer not in (None, ""):
                    errors.append(
                        f"{field_where}: a date field with status={status!r} must not "
                        "also carry an answer; omit the nonexistent date."
                    )

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
