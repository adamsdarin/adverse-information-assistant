#!/usr/bin/env python3
"""Validate corpus integrity. CI-gating: exit nonzero on any error.

Checks:
- SEAD 4 files: frontmatter complete; warns on verbatim: false (scaffold state)
- DOHA case files: required frontmatter keys, valid guideline letters, valid
  outcome/level, doha.ogc.osd.mil source_url
- Reporting tables: parseable YAML, unique entry IDs, channel_refs resolve,
  warns on maintainer_verified: false
- Checklists: parseable, guideline set, unique element ids
- index.json is in sync with case files (run build_index.py first)

A verification claim requires provenance. Any file asserting
maintainer_verified: true (or verbatim: true for SEAD 4 texts) must also carry
source_url, source_sha256, and verified_date — otherwise the claim is an
unauthenticated flag anyone can flip in a fork. Compute the hash of the
official source document with scripts/hash_source.py.

Usage: python scripts/validate_corpus.py [--corpus PATH]
Requires: pyyaml
"""
import json
import sys
from pathlib import Path

import yaml

import corpus_paths

_corpus_flag = None
if "--corpus" in sys.argv:
    _corpus_flag = sys.argv[sys.argv.index("--corpus") + 1]
CORPUS = corpus_paths.require(_corpus_flag)
GUIDELINES = set("ABCDEFGHIJKLM")
errors: list[str] = []
warnings: list[str] = []

PROVENANCE_KEYS = ("source_url", "source_sha256", "verified_date")


def require_provenance(data: dict, path: Path, claim_key: str) -> None:
    """A verified flag without provenance is an error, not a warning.

    The flag says a human checked this file against its official source. The
    provenance keys are what make that claim auditable: which source, which
    exact bytes (SHA-256 of the source document), and when. Without them the
    flag is a social claim wearing a technical costume.
    """
    if not data.get(claim_key):
        return
    missing = [k for k in PROVENANCE_KEYS if not data.get(k)]
    if missing:
        errors.append(
            f"{path}: {claim_key}=true without provenance "
            f"(missing: {', '.join(missing)}). A verification claim must record "
            "source_url, source_sha256 (see scripts/hash_source.py), and "
            "verified_date — otherwise the flag is unauditable."
        )


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        errors.append(f"{path}: missing YAML frontmatter")
        return {}
    try:
        _, fm, _ = text.split("---", 2)
        return yaml.safe_load(fm) or {}
    except Exception as e:  # noqa: BLE001
        errors.append(f"{path}: unparseable frontmatter ({e})")
        return {}


def check_sead4() -> None:
    for path in sorted((CORPUS / "sead4").glob("*.md")):
        if path.name.startswith("_"):
            continue
        fm = frontmatter(path)
        for key in ("guideline", "title", "source_url"):
            if not fm.get(key):
                errors.append(f"{path}: missing frontmatter key '{key}'")
        if fm.get("guideline") not in GUIDELINES:
            errors.append(f"{path}: invalid guideline '{fm.get('guideline')}'")
        if not fm.get("verbatim"):
            warnings.append(f"{path}: verbatim=false — UNCITEABLE until official text is pasted")
        require_provenance(fm, path, "verbatim")


def check_cases() -> list[dict]:
    cases = []
    for path in sorted((CORPUS / "doha" / "cases").glob("*.md")):
        if path.name.startswith("_"):
            continue
        fm = frontmatter(path)
        for key in ("case_no", "decided", "guidelines", "outcome", "level", "source_url"):
            if key not in fm:
                errors.append(f"{path}: missing frontmatter key '{key}'")
        for g in fm.get("guidelines", []):
            if g not in GUIDELINES:
                errors.append(f"{path}: invalid guideline tag '{g}'")
        if fm.get("outcome") not in ("granted", "denied", "remanded"):
            errors.append(f"{path}: invalid outcome '{fm.get('outcome')}'")
        if fm.get("level") not in ("hearing", "appeal"):
            errors.append(f"{path}: invalid level '{fm.get('level')}'")
        url = str(fm.get("source_url", ""))
        if "doha.ogc.osd.mil" not in url:
            errors.append(f"{path}: source_url must point to doha.ogc.osd.mil")
        cases.append(fm)
    return cases


def check_reporting() -> None:
    tables_dir = CORPUS / "reporting" / "tables"
    channels: set[str] = set()
    ch_file = tables_dir / "channels.yaml"
    if ch_file.exists():
        data = yaml.safe_load(ch_file.read_text(encoding="utf-8")) or {}
        # Channels are scoped by population: industry uses FSO/DISS/CISA,
        # federal and military use their servicing security office. A
        # channel_ref may resolve against either family.
        channels = set(data.get("industry_channels", {})) | set(
            data.get("federal_military_channels", {})
        )
        if not channels and "channels" in data:
            errors.append(
                f"{ch_file}: uses the old flat 'channels' key. Channels must be split into "
                "industry_channels and federal_military_channels — routing a federal user "
                "to DISS sends them to a system they cannot access."
            )
        for required in ("industry_channels", "federal_military_channels"):
            if required not in data:
                errors.append(f"{ch_file}: missing '{required}'")
        if not data.get("maintainer_verified"):
            warnings.append(f"{ch_file}: maintainer_verified=false — advisor must return consult_fso")
        require_provenance(data, ch_file, "maintainer_verified")
    seen_ids: set[str] = set()
    for path in sorted(tables_dir.glob("*.yaml")):
        if path.name == "channels.yaml":
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not data.get("maintainer_verified"):
            warnings.append(f"{path}: maintainer_verified=false — UNCITEABLE until verified against the ISL")
        require_provenance(data, path, "maintainer_verified")
        for entry in data.get("entries", []):
            eid = entry.get("id")
            if not eid:
                errors.append(f"{path}: entry missing id")
                continue
            if eid in seen_ids:
                errors.append(f"{path}: duplicate entry id '{eid}'")
            seen_ids.add(eid)
            ref = entry.get("channel_ref")
            if ref and channels and ref not in channels:
                errors.append(f"{path}: entry '{eid}' channel_ref '{ref}' not in channels.yaml")
            if entry.get("reportable") not in ("yes", "no", "consult_fso"):
                errors.append(f"{path}: entry '{eid}' invalid reportable value")


def check_authority_layers() -> None:
    """SEAD 3 must cover every population; the ISL must not over-reach."""
    path = CORPUS / "reporting" / "authority-layers.yaml"
    if not path.exists():
        errors.append(f"{path}: missing — the SEAD 3 / ISL layer split is not optional")
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    layers = data.get("layers", {})
    for required in ("sead-3", "isl-2021-02"):
        if required not in layers:
            errors.append(f"{path}: missing layer '{required}'")

    p2l = data.get("population_to_layers", {})
    for pop in ("industry", "federal_civilian", "military"):
        applied = p2l.get(pop)
        if not applied:
            errors.append(f"{path}: population '{pop}' has no layers")
            continue
        if "sead-3" not in applied:
            errors.append(
                f"{path}: population '{pop}' omits sead-3. SEAD 3 binds EVERY covered "
                "individual — omitting it produces a missed report."
            )
        if pop != "industry" and "isl-2021-02" in applied:
            errors.append(
                f"{path}: population '{pop}' includes isl-2021-02, which reaches "
                "NISP contractors only."
            )
    if data.get("attribution_status") != "complete":
        warnings.append(
            f"{path}: attribution_status={data.get('attribution_status')!r} — table entries "
            "are not attributed to a layer; federal/military users degrade to consult_fso"
        )


def check_checklists() -> None:
    for path in sorted((CORPUS / "checklists").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if data.get("guideline") not in GUIDELINES:
            errors.append(f"{path}: invalid or missing guideline")
        if not data.get("sources"):
            errors.append(f"{path}: 'sources' is required")
        ids = [e.get("id") for e in data.get("elements", [])]
        if len(ids) != len(set(ids)):
            errors.append(f"{path}: duplicate element ids")
        if not ids:
            errors.append(f"{path}: no elements")
        if not data.get("maintainer_verified"):
            warnings.append(f"{path}: maintainer_verified=false — REVIEW DRAFT, questions unvetted")
        require_provenance(data, path, "maintainer_verified")
        check_followups(data, path)
        check_granularity(data, path)
        check_coverage(data, path)
        uni = data.get("universal")
        if uni and not (CORPUS / "checklists" / uni).exists():
            errors.append(f"{path}: universal file '{uni}' not found")
        sev = data.get("severity_default")
        if sev and sev not in ("low", "medium", "high"):
            errors.append(f"{path}: invalid severity_default '{sev}'")


VALID_TRIGGERS = {"always", "vague", "answered_yes", "answered_no",
                  "pending", "quantitative_tension"}
# Every guideline, not a subset. The five high-frequency ones were made granular
# first; the rest followed. A future checklist that reverts to bundled asks is a
# regression and gets flagged as one.
GRANULAR_REQUIRED = set(GUIDELINES)


# ---------------------------------------------------------------------------
# THE COVERAGE SPINE — who / what / when / where / why / how / future intent
# ---------------------------------------------------------------------------
_coverage_spec_cache: dict | None = None


def coverage_spec() -> dict:
    """Load _COVERAGE.yaml once. It is the authority for the facet names."""
    global _coverage_spec_cache
    if _coverage_spec_cache is None:
        path = CORPUS / "checklists" / "_COVERAGE.yaml"
        if not path.exists():
            errors.append(f"{path}: missing — the coverage spine is unenforced")
            _coverage_spec_cache = {}
        else:
            _coverage_spec_cache = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _coverage_spec_cache


def check_coverage(data: dict, path: Path) -> None:
    """A checklist must be able to answer the questions any report answers.

    Granularity gets the facts. Coverage proves the facts add up to an account.
    A checklist that collects nine precise details about a court disposition and
    never asks why the thing happened is not 90% complete — it reads as evasive
    on the one it skipped, because a reader cannot distinguish "nothing to say"
    from "not saying it".
    """
    spec = coverage_spec()
    if not spec:
        return
    known = {f.get("id") for f in spec.get("facets", []) if isinstance(f, dict)}
    required = list(spec.get("required_facets", []))
    inheritable = set(spec.get("inheritable_from_universal", []))

    covered: set[str] = set()
    covered_by_required_element: set[str] = set()
    for el in data.get("elements", []):
        if not isinstance(el, dict):
            continue
        facets = el.get("covers")
        if facets is None:
            errors.append(
                f"{path}: element '{el.get('id')}' has no 'covers' — every element "
                f"declares which of {sorted(known)} it carries"
            )
            continue
        if not isinstance(facets, list):
            errors.append(f"{path}: element '{el.get('id')}' covers must be a list")
            continue
        for f in facets:
            if f not in known:
                # Same failure mode as an unknown followup trigger: it satisfies
                # nothing and hides the gap it was meant to close.
                errors.append(
                    f"{path}: element '{el.get('id')}' covers {f!r}, which is not a "
                    f"facet in _COVERAGE.yaml — it satisfies nothing"
                )
                continue
            covered.add(f)
            if el.get("criticality") == "required":
                covered_by_required_element.add(f)

    if "how_relevant" not in data:
        errors.append(
            f"{path}: must declare how_relevant (true or false). Mechanism is what a "
            "reviewer reads for; silence on whether it applies is not permitted"
        )
    if data.get("how_relevant") is False and not str(data.get("how_not_relevant_because", "")).strip():
        errors.append(
            f"{path}: how_relevant is false but how_not_relevant_because is empty — "
            "declining a facet requires the reason in prose"
        )

    for facet in required:
        if facet in covered:
            if facet not in covered_by_required_element and facet not in inheritable:
                warnings.append(
                    f"{path}: facet '{facet}' is carried only by optional elements — "
                    "it disappears silently if the user declines them"
                )
            continue
        if facet in inheritable and data.get("universal"):
            continue
        if facet == "how" and data.get("how_relevant") is False:
            continue
        errors.append(f"{path}: no element covers the '{facet}' facet")


# ---------------------------------------------------------------------------
# THE REPORTING AXIS — every reportable event has questions behind it
# ---------------------------------------------------------------------------
def check_event_checklists() -> None:
    """Reportable events do not map 1:1 onto SEAD 4 guidelines, so they get
    their own checklists — and every entry in the reporting tables must be
    claimed by exactly one of them.

    Not zero: an unclaimed table entry is a reportable matter with no questions
    behind it, which is precisely the gap that let unofficial foreign travel —
    the only obligation in the scheme that has to be met BEFORE the event — go
    unasked for months.

    Not two: duplicate claims mean two files drift and one of them silently
    loses.
    """
    events_dir = CORPUS / "checklists" / "events"
    if not events_dir.is_dir():
        errors.append(f"{events_dir}: missing — the reporting axis is unimplemented")
        return

    # What the tables actually require, which is the authority here.
    table_ids: dict[str, Path] = {}
    for tpath in sorted((CORPUS / "reporting" / "tables").glob("*.yaml")):
        tdata = yaml.safe_load(tpath.read_text(encoding="utf-8")) or {}
        for entry in tdata.get("entries", []) or []:
            if isinstance(entry, dict) and entry.get("id"):
                table_ids[entry["id"]] = tpath

    channels = yaml.safe_load(
        (CORPUS / "reporting" / "tables" / "channels.yaml").read_text(encoding="utf-8")
    ) or {}
    known_channels = set()
    for group in ("industry_channels", "federal_military_channels", "applicant_channels"):
        known_channels |= set((channels.get(group) or {}).keys())

    claimed: dict[str, list[str]] = {}
    for path in sorted(events_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        name = data.get("event_checklist")
        if name != path.stem:
            errors.append(f"{path}: event_checklist '{name}' does not match the filename")
        if not data.get("sources"):
            errors.append(f"{path}: 'sources' is required")
        ids = [e.get("id") for e in data.get("elements", []) if isinstance(e, dict)]
        if not ids:
            errors.append(f"{path}: no elements")
        if len(ids) != len(set(ids)):
            errors.append(f"{path}: duplicate element ids")
        if not data.get("maintainer_verified"):
            warnings.append(f"{path}: maintainer_verified=false — REVIEW DRAFT, questions unvetted")
        require_provenance(data, path, "maintainer_verified")
        check_followups(data, path)
        check_coverage(data, path)

        evs = data.get("event_ids")
        if evs is None:
            errors.append(f"{path}: 'event_ids' is required (use [] with no_table_entry_because)")
            evs = []
        if not evs and not str(data.get("no_table_entry_because", "")).strip():
            errors.append(
                f"{path}: claims no table entry but gives no no_table_entry_because — "
                "an event checklist with no authority behind it must say so in prose"
            )
        if not evs and data.get("reportability_default") != "consult_fso":
            errors.append(
                f"{path}: has no table entry, so reportability_default must be "
                "'consult_fso' — the tool does not assert an obligation it cannot cite"
            )
        for ev in evs:
            if ev not in table_ids:
                errors.append(f"{path}: event id '{ev}' is in no reporting table")
            claimed.setdefault(ev, []).append(path.name)

        for g in data.get("guidelines", []) or []:
            if g not in GUIDELINES:
                errors.append(f"{path}: guideline '{g}' is not a SEAD 4 guideline")
            elif not (CORPUS / "checklists" / f"guideline-{g}.yaml").exists():
                errors.append(f"{path}: guideline '{g}' has no checklist file")
        for ch in data.get("channel_refs", []) or []:
            if ch not in known_channels:
                errors.append(f"{path}: channel_ref '{ch}' is not defined in channels.yaml")

    for ev, tpath in sorted(table_ids.items()):
        who = claimed.get(ev, [])
        if not who:
            errors.append(
                f"{tpath}: reportable event '{ev}' is claimed by no event checklist — "
                "a reporting obligation with no questions behind it"
            )
        elif len(who) > 1:
            errors.append(
                f"reportable event '{ev}' is claimed by more than one event checklist "
                f"({', '.join(who)}) — the two will drift and one will lose"
            )


def check_followups(data: dict, path: Path) -> None:
    """Conditional question ladders.

    A followup with an unknown trigger never fires — the question silently
    disappears and the gap it was meant to close reappears as an agency
    request weeks later. So an unknown trigger is an error, not a warning.
    """
    for el in data.get("elements", []):
        if not isinstance(el, dict):
            continue
        fups = el.get("followups")
        if fups is None:
            continue
        if not isinstance(fups, list):
            errors.append(f"{path}: element '{el.get('id')}' followups must be a list")
            continue
        for i, f in enumerate(fups):
            where = f"{path}: element '{el.get('id')}' followup[{i}]"
            if not isinstance(f, dict):
                errors.append(f"{where}: must be a mapping")
                continue
            if f.get("trigger") not in VALID_TRIGGERS:
                errors.append(
                    f"{where}: trigger {f.get('trigger')!r} is not one of "
                    f"{sorted(VALID_TRIGGERS)} — it would never fire"
                )
            if not str(f.get("ask", "")).strip():
                errors.append(f"{where}: has no 'ask'")


def check_granularity(data: dict, path: Path) -> None:
    """The high-frequency guidelines must be question-per-fact.

    A bundled ask returns one answer and loses the rest, which is how a
    package reaches an adjudicator with holes in it.
    """
    g = data.get("guideline")
    if g not in GRANULAR_REQUIRED:
        return
    els = data.get("elements", [])
    if not any(e.get("followups") for e in els if isinstance(e, dict)):
        warnings.append(
            f"{path}: guideline {g} is in the granular set but has no "
            "conditional followups — check it was not reverted to bundled asks"
        )
    for el in els:
        if not isinstance(el, dict):
            continue
        q = str(el.get("ask", ""))
        # Three or more comma-separated clauses in one ask is the shape of a
        # bundled question. Two is usually a legitimate either/or.
        if q.count(",") >= 3 and "—" in q:
            warnings.append(
                f"{path}: element '{el.get('id')}' may bundle several facts "
                f"into one question: {q[:70]!r}"
            )


def check_entity_capture() -> None:
    """The name-and-location fields both questionnaires demand.

    A beta session worked out the right court and never asked for its address,
    the arresting agency's address, or the venue. Those are form fields and
    retrieval anchors; missing them produces a package an FSO cannot act on.
    """
    path = CORPUS / "forms" / "entity-capture.yaml"
    if not path.exists():
        errors.append(f"{path}: missing — the forms' entity/location fields are unenforced")
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ents = {e.get("id") for e in data.get("entities", []) if isinstance(e, dict)}
    for required in ("offense-location", "citing-agency",
                     "arresting-agency-if-different", "court", "venue"):
        if required not in ents:
            errors.append(f"{path}: missing entity '{required}'")
    for e in data.get("entities", []):
        if not isinstance(e, dict):
            continue
        if not e.get("ask"):
            errors.append(f"{path}: entity '{e.get('id')}' has no 'ask'")
    # The citing/arresting split is the finding this file exists to encode.
    blob = path.read_text(encoding="utf-8").lower()
    if "booking" not in blob or "sheriff" not in blob:
        errors.append(
            f"{path}: must explain that the citing agency and the arresting or "
            "booking agency can differ — a records request goes to whichever "
            "agency created the record"
        )
    require_provenance(data, path, "maintainer_verified")

    # Checklist elements referencing an entity must reference one that exists.
    for cl in sorted((CORPUS / "checklists").glob("guideline-*.yaml")):
        d = yaml.safe_load(cl.read_text(encoding="utf-8")) or {}
        for el in d.get("elements", []):
            ref = isinstance(el, dict) and el.get("entity_ref")
            if ref and ref not in ents:
                errors.append(f"{cl}: element '{el.get('id')}' references unknown "
                              f"entity '{ref}'")


def check_collection_policy() -> None:
    """Which form standard the tool collects to, and the one-line switch."""
    path = CORPUS / "forms" / "collection-policy.yaml"
    if not path.exists():
        errors.append(f"{path}: missing")
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    std = data.get("collection_standard")
    if std not in ("sf86", "pvq"):
        errors.append(f"{path}: collection_standard is {std!r}; must be 'sf86' or 'pvq'")
    diffs = data.get("material_differences", {})
    for required in ("criminal_lookback", "traffic_fine_threshold"):
        if required not in diffs:
            errors.append(
                f"{path}: material_differences must record '{required}' — the two "
                "forms differ on it and using the wrong one produces a wrong answer"
            )
    if std == "sf86" and data.get("pvq_status") != "not_fully_launched":
        warnings.append(
            f"{path}: collection_standard is 'sf86' but pvq_status is "
            f"{data.get('pvq_status')!r} — if the PVQ has launched, flip the switch"
        )


def check_plausibility() -> None:
    path = CORPUS / "checks" / "plausibility.yaml"
    if not path.exists():
        warnings.append(f"{path}: missing — quantitative tension checks unavailable")
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ids = set()
    for c in data.get("checks", []):
        cid = c.get("id")
        if not cid:
            errors.append(f"{path}: a check has no id")
            continue
        if cid in ids:
            errors.append(f"{path}: duplicate check id '{cid}'")
        ids.add(cid)
        for key in ("applies_to", "trigger_when", "say"):
            if not c.get(key):
                errors.append(f"{path}: check '{cid}' missing '{key}'")
    # The hard rule: the tool must never assert a computed BAC.
    blob = path.read_text(encoding="utf-8").lower()
    if "never_say" not in blob or "blood alcohol" not in blob:
        errors.append(
            f"{path}: must carry an explicit prohibition on stating a computed "
            "blood alcohol figure — that is the whole guardrail on this check"
        )
    require_provenance(data, path, "maintainer_verified")


def check_universal() -> None:
    path = CORPUS / "checklists" / "_UNIVERSAL.yaml"
    if not path.exists():
        errors.append(f"{path}: missing — every guideline checklist depends on it")
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ids = [e.get("id") for e in data.get("elements", [])]
    if len(ids) != len(set(ids)):
        errors.append(f"{path}: duplicate element ids")
    for required in ("others-aware-count", "others-aware-roles", "coercion-exposure"):
        if required not in ids:
            errors.append(f"{path}: required universal element '{required}' missing")
    if not data.get("maintainer_verified"):
        warnings.append(f"{path}: maintainer_verified=false — REVIEW DRAFT")
    require_provenance(data, path, "maintainer_verified")


def check_severity_ladders() -> None:
    """The depth-scaling framework: one entry per guideline, each tier's
    signal_elements pointing at real ids in that guideline's own checklist.

    This file replaces each guideline's flat severity_default with a tier
    computed from facts the user already stated. It adds no new questions —
    every signal_elements id must already exist in guideline-<X>.yaml, or
    the tier is pointing the interviewer at a question that was never asked.
    """
    path = CORPUS / "checklists" / "_SEVERITY_LADDERS.yaml"
    if not path.exists():
        errors.append(f"{path}: missing — depth scaling has no case-grounded basis, "
                       "falls back to each checklist's flat severity_default")
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not data.get("maintainer_verified"):
        warnings.append(f"{path}: maintainer_verified=false — REVIEW DRAFT, "
                         "case citations unvetted")
    require_provenance(data, path, "maintainer_verified")

    guidelines = data.get("guidelines", {})
    missing = GUIDELINES - set(guidelines)
    if missing:
        errors.append(f"{path}: no entry for guideline(s) {sorted(missing)}")

    real_ids: dict[str, set] = {}
    for g, entry in guidelines.items():
        if g not in GUIDELINES:
            errors.append(f"{path}: '{g}' is not a valid guideline letter")
            continue
        gpath = CORPUS / "checklists" / f"guideline-{g}.yaml"
        if gpath not in real_ids:
            if not gpath.exists():
                errors.append(f"{path}: guideline-{g}.yaml not found for cross-check")
                real_ids[gpath] = set()
            else:
                gdata = yaml.safe_load(gpath.read_text(encoding="utf-8")) or {}
                real_ids[gpath] = {e.get("id") for e in gdata.get("elements", [])}

        ladder = entry.get("ladder", True)
        if ladder:
            tiers = entry.get("tiers") or []
            if not tiers:
                errors.append(f"{path}: {g} has ladder: true but no tiers")
            for tier in tiers:
                if tier.get("depth") not in ("low", "medium", "high"):
                    errors.append(f"{path}: {g} tier '{tier.get('name')}' has invalid "
                                   f"depth {tier.get('depth')!r}")
                if not tier.get("defining_facts") and not tier.get("note"):
                    errors.append(f"{path}: {g} tier '{tier.get('name')}' has no "
                                   "defining_facts or note")
        else:
            if not entry.get("fact_dimensions"):
                errors.append(f"{path}: {g} has ladder: false but no fact_dimensions "
                               "— thin guidelines still need something to ask from")
            if not entry.get("reason_thin"):
                warnings.append(f"{path}: {g} has ladder: false with no reason_thin "
                                 "stated — a thin sample should say so")

        entries = entry.get("tiers", []) + entry.get("fact_dimensions", []) \
            + entry.get("modifiers", [])
        for sub in entries:
            for sid in sub.get("signal_elements", []):
                if sid not in real_ids[gpath]:
                    errors.append(f"{path}: {g} signal_elements references "
                                   f"'{sid}', which is not an element id in "
                                   f"guideline-{g}.yaml — question drifted or was renamed")

    axis = data.get("universal_axis", {})
    axis_guidelines = set(axis.get("by_guideline", {}))
    missing_axis = GUIDELINES - axis_guidelines
    if missing_axis:
        warnings.append(f"{path}: universal_axis.by_guideline has no entry for "
                         f"{sorted(missing_axis)}")

    uni_path = CORPUS / "checklists" / "_UNIVERSAL.yaml"
    if uni_path.exists():
        uni_data = yaml.safe_load(uni_path.read_text(encoding="utf-8")) or {}
        uni_ids = {e.get("id") for e in uni_data.get("elements", [])}
        axis_id = axis.get("id")
        if axis_id and axis_id not in uni_ids:
            errors.append(f"{path}: universal_axis.id '{axis_id}' is not an "
                           "element in _UNIVERSAL.yaml")


def check_document_evidence() -> None:
    """The DOHA-case-grounded catalog of what documents judges actually
    treated as persuasive, per guideline — what documents-advisor.md reads
    instead of defaulting to a court/police pattern that doesn't generalize.
    """
    path = CORPUS / "checklists" / "_DOCUMENT_EVIDENCE.yaml"
    if not path.exists():
        errors.append(f"{path}: missing — documents-advisor.md has no "
                       "case-grounded basis for what to recommend")
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not data.get("maintainer_verified"):
        warnings.append(f"{path}: maintainer_verified=false — REVIEW DRAFT, "
                         "case citations unvetted")
    require_provenance(data, path, "maintainer_verified")

    guidelines = data.get("guidelines", {})
    missing = GUIDELINES - set(guidelines)
    if missing:
        errors.append(f"{path}: no entry for guideline(s) {sorted(missing)}")

    for g, entry in guidelines.items():
        if g not in GUIDELINES:
            errors.append(f"{path}: '{g}' is not a valid guideline letter")
            continue
        docs = entry.get("documents") or []
        bare = entry.get("bare_claim_pattern") or []
        if not docs and not entry.get("note"):
            errors.append(f"{path}: {g} has no documents and no explanatory "
                           "note — say the sample was thin rather than leaving it empty")
        for d in docs:
            if d.get("weight") not in ("strong", "moderate", "weak"):
                errors.append(f"{path}: {g} document '{d.get('type')}' has "
                               f"invalid weight {d.get('weight')!r}")
            if not d.get("corroborates") or not d.get("custodian"):
                errors.append(f"{path}: {g} document '{d.get('type')}' is "
                               "missing corroborates or custodian")
        for b in bare:
            if not b.get("finding") or not b.get("case_ref"):
                errors.append(f"{path}: {g} bare_claim_pattern entry missing "
                               "finding or case_ref")


def check_courts() -> None:
    """The court recognition aid. A memory jog, held to the same provenance
    rule as everything else: a state may not be marked verified without a
    source and a date."""
    path = CORPUS / "courts" / "state-courts.yaml"
    if not path.exists():
        warnings.append(f"{path}: missing — the court recognition aid is unavailable, "
                        "so the interviewer can only fall back to 'contact the clerk'")
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    states = data.get("states", {})
    if not states:
        errors.append(f"{path}: no states defined")
        return
    required = ("name", "trial_court_felony", "trial_court_misdemeanor",
                "organized_by", "unit_label", "records_custodian", "judiciary_url")
    unverified = 0
    for code, st in sorted(states.items()):
        if not isinstance(st, dict):
            errors.append(f"{path}: entry '{code}' is not a mapping")
            continue
        if len(code) != 2 or not code.isupper():
            errors.append(f"{path}: '{code}' should be a two-letter uppercase code")
        for key in required:
            if not st.get(key):
                errors.append(f"{path}: {code} missing '{key}'")
        if st.get("verified"):
            missing = [k for k in ("source_url", "verified_date") if not st.get(k)]
            if missing:
                errors.append(
                    f"{path}: {code} is marked verified without provenance "
                    f"(missing: {', '.join(missing)}). A verification claim must "
                    "record where and when it was checked."
                )
        else:
            unverified += 1
    if len(states) < 51:
        warnings.append(f"{path}: only {len(states)} jurisdictions — 50 states + DC expected")
    if unverified:
        warnings.append(
            f"{path}: {unverified}/{len(states)} jurisdictions unverified — the "
            "interviewer must offer these explicitly as guesses, never assert them"
        )


def check_index(cases: list[dict]) -> None:
    index_path = CORPUS / "doha" / "index.json"
    if not index_path.exists():
        errors.append(f"{index_path}: missing — run scripts/build_index.py")
        return
    index = json.loads(index_path.read_text(encoding="utf-8"))
    indexed = {c["case_no"] for c in index.get("cases", [])}
    on_disk = {c.get("case_no") for c in cases}
    if indexed != on_disk:
        errors.append("index.json out of sync with corpus/doha/cases — run scripts/build_index.py")


def main() -> int:
    check_sead4()
    cases = check_cases()
    check_reporting()
    check_authority_layers()
    check_checklists()
    check_event_checklists()
    check_universal()
    check_severity_ladders()
    check_document_evidence()
    check_courts()
    check_entity_capture()
    check_collection_policy()
    check_plausibility()
    check_index(cases)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
