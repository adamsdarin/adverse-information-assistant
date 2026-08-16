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
        uni = data.get("universal")
        if uni and not (CORPUS / "checklists" / uni).exists():
            errors.append(f"{path}: universal file '{uni}' not found")
        sev = data.get("severity_default")
        if sev and sev not in ("low", "medium", "high"):
            errors.append(f"{path}: invalid severity_default '{sev}'")


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
    check_universal()
    check_courts()
    check_index(cases)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
