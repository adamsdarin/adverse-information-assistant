#!/usr/bin/env python3
"""Build the hosted MCP reference release (`mcp/release/`) from the approved
DCSA Library release and this checkout. Design: docs/HOSTED-MCP-DESIGN.md §1.4
and §5.3.

The hosted server at fsotools.ai/adverse/mcp serves three kinds of file, and
this script is the only thing that produces them:

  government/<directive>/…   SEAD 4, SEAD 3 and ISL 2021-02 section splits,
                             copied byte-for-byte from the approved library
                             release and re-verified against the Archivist's
                             own body hashes. 32 CFR Part 117 only when the
                             library carries a section split (decision D5).
  corpus/…                   the maintainer-authored files from ./corpus,
                             YAML converted to JSON, each stamped with the
                             SHA-256 of the YAML it came from. Their
                             maintainer_verified flags are served AS THEY ARE.
  agents/…                   the agent prompts, verbatim, for MCP prompts/list.
  doha-exclusions.json       document ids the library marks answer_eligible
                             false, so find_decisions can exclude them (D7).
  manifest.json              release ids, approval receipt, SHA-256 of every
                             file above. The Worker verifies each asset
                             against it once per isolate and fails closed.

Rules, all of which refuse rather than warn (exit 2):
  * the library release must pass release_contract.approved_release —
    an unapproved library is not a source;
  * every Government section's body hash must match the library manifest;
  * validate_corpus.py and tests/run_tests.py must pass on this checkout
    (--skip-checks exists for the test suite, which calls this script);
  * THIS SCRIPT FETCHES NOTHING. Inputs are the library root on disk and the
    checkout. never_auto_fetch applies here exactly as it does to agents.
  * it never changes a maintainer_verified value, and never commits.

Usage:
  python scripts/hosted_release.py --library "<library root>" --dry-run
  python scripts/hosted_release.py --library "<library root>"
  python scripts/hosted_release.py --library "<root>" --doha-shards s1,s2,s3 --deploy

Exit codes: 0 built/deployed or nothing changed · 2 refused · 3 deployed but
the live get_release does not report the new ids.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

# Windows consoles may default to cp1252; the summary uses em-dashes and §.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import library_paths as lp  # noqa: E402
import release_contract as rc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
AGENTS = ROOT / "agents"
DEFAULT_OUT = ROOT / "mcp" / "release"
DEFAULT_CONFIG = ROOT / "mcp" / "wrangler.jsonc"
WORKER_NAME = "adverse-information-assistant"

EXIT_OK, EXIT_REFUSED, EXIT_LIVE_MISMATCH = 0, 2, 3

# Government text: directive key -> (library folder, release folder)
DIRECTIVES = {
    "sead-4": (lp.SEAD4_DIR, "government/sead-4"),
    "sead-3": (lp.SEAD3_DIR, "government/sead-3"),
    "isl-2021-02": (lp.ISL_SPLIT_DIR, "government/isl-2021-02"),
}
CFR_DIR = "ROBOT_READABLE_DIRECTORY/TEXT/AUTHORITIES/CFR"
CFR_RELEASE_DIR = "government/cfr-117"
CFR_UNAVAILABLE_REASON = (
    "The approved library release carries 32 CFR Part 117 as one unsplit "
    "file. This tool serves directive text one section at a time and does "
    "not slice a whole regulation itself; §117.8 becomes available when the "
    "DCSA Archivist publishes a section split of the Part (owner decision D5)."
)

# Maintainer-authored files published (design §1.3). Paths relative to corpus/.
# NOT published: sead4/*.md, reporting/*.md, doha/, _TEMPLATE files, README,
# BUILDING.md, reporting-channels.yaml.ref.
MAINTAINER_FILES = [
    "reporting/authority-layers.yaml",
    "reporting/tables/all-covered-individuals.yaml",
    "reporting/tables/adverse-information.yaml",
    "reporting/tables/top-secret-q.yaml",
    "reporting/tables/channels.yaml",
    *[f"checklists/guideline-{g}.yaml" for g in "ABCDEFGHIJKLM"],
    "checklists/_UNIVERSAL.yaml",
    "checklists/_COVERAGE.yaml",
    "checklists/_INCIDENT_CHRONOLOGY.yaml",
    "checklists/_INCIDENT_PROFILES.yaml",
    "checklists/_SEVERITY_LADDERS.yaml",
    "checklists/_DOCUMENT_EVIDENCE.yaml",
    "checklists/events/_INDEX.yaml",
    *sorted(f"checklists/events/{p.name}" for p in (CORPUS / "checklists" / "events").glob("event-*.yaml")),
    "forms/collection-policy.yaml",
    "forms/sf86-map.yaml",
    "forms/pvq-map.yaml",
    "forms/incident-report-map.yaml",
    "forms/entity-capture.yaml",
    "forms/diss-incident-types.yaml",
    "forms/pvq-preambles.md",
    "courts/state-courts.yaml",
    "privacy-tiers.yaml",
    "checks/plausibility.yaml",
]
PROVENANCE_KEYS = ("source_url", "source_sha256", "verified_date")

UNVERIFIED_SENTENCE = (
    "This file is maintainer-authored and not yet verified against its "
    "official source, so it cannot ground a 'yes'. Treat the matter as "
    "'consult your security office' until a maintainer verifies it."
)


class Refused(Exception):
    """Anything that stops the build. Printed, then exit 2."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump_json(data) -> bytes:
    return (json.dumps(data, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def repo_commit() -> tuple[str, bool]:
    try:
        short = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no",
                                     "--", "corpus", "agents", "scripts", "mcp", "DISCLAIMER.md"],
                                    cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip())
        return short, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


# ---------------------------------------------------------------------------
# Government text
# ---------------------------------------------------------------------------
def section_body(doc: str) -> str:
    """The text the Archivist's body_sha256 covers.

    directive_splits.py writes `<header>\\n\\n---\\n\\n<text>\\n` where text is the
    section body stripped of surrounding newlines, and hashes `text`. Recover
    it the same way: everything after the first rule line, stripped of
    newlines at both ends. Line endings are normalised first, as a text-mode
    read would, so a checkout with CRLF endings hashes the same text.
    """
    lines = doc.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "---" and i > 0:
            return "\n".join(lines[i + 1:]).strip("\n")
    raise Refused("section file has no header/body separator")


def collect_directive(root: Path, key: str, files: dict, out: Path) -> dict:
    lib_dir, rel_dir = DIRECTIVES[key]
    manifest_path, _ = lp.find_ci(root, f"{lib_dir}/manifest.json")
    if not manifest_path or not manifest_path.is_file():
        raise Refused(f"{key}: no section split in the library release ({lib_dir}/manifest.json). "
                      "Needs a refreshed DCSA Archivist release.")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    sections = manifest.get("sections") or []
    if not sections:
        raise Refused(f"{key}: the split manifest lists no sections")
    (out / rel_dir).mkdir(parents=True, exist_ok=True)
    (out / rel_dir / "manifest.json").write_bytes(manifest_bytes)
    files[f"{rel_dir}/manifest.json"] = {
        "sha256": sha256_bytes(manifest_bytes),
        "source": f"library:{lib_dir}/manifest.json",
        "verified": True, "verified_by": "custodian-release",
    }
    for sec in sections:
        name = sec.get("file")
        if not name or "/" in name or "\\" in name or name.startswith("."):
            raise Refused(f"{key}: manifest names an unsafe section file")
        src, _ = lp.find_ci(root, f"{lib_dir}/{name}")
        if not src or not src.is_file():
            raise Refused(f"{key}: {name} is listed in the manifest but not on disk")
        raw = src.read_bytes()
        expected = sec.get("body_sha256")
        if not expected:
            # A section the library manifest does not hash cannot be served as
            # "verified by the Custodian release": there is nothing to verify it
            # against. Refuse rather than fail open.
            raise Refused(f"{key}: {name} carries no body_sha256 in the library manifest, so it cannot be verified")
        actual = sha256_bytes(section_body(raw.decode("utf-8-sig")).encode("utf-8"))
        if actual != expected:
            raise Refused(f"{key}: {name} does not match the body hash the library manifest records")
        (out / rel_dir / name).write_bytes(raw)
        files[f"{rel_dir}/{name}"] = {
            "sha256": sha256_bytes(raw),
            "source": f"library:{lib_dir}/{name}",
            "body_sha256": expected,
            "verified": True, "verified_by": "custodian-release",
        }
    extra = {"source_sha256": manifest.get("source_sha256"),
             "generated_utc": manifest.get("generated_utc")}
    return {"manifest": f"{rel_dir}/manifest.json", "sections": len(sections), **extra}


def find_cfr_split(root: Path) -> tuple[Path | None, dict | None]:
    """A section split of 32 CFR Part 117, if the Archivist has published one.

    Recognised by a manifest.json under the CFR folder whose `directive` names
    Part 117 and whose sections include §117.8. The whole-Part text file is
    never read here: slicing it is the exact thing this build refuses to do.
    """
    cfr, _ = lp.find_ci(root, CFR_DIR)
    if not cfr or not cfr.is_dir():
        return None, None
    for child in sorted(p for p in cfr.iterdir() if p.is_dir()):
        mp = child / "manifest.json"
        if not mp.is_file():
            continue
        try:
            m = json.loads(mp.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        directive = re.sub(r"[^a-z0-9]+", "", str(m.get("directive", "")).lower())
        if directive not in ("32cfr117", "32cfrpart117", "cfr117"):
            continue
        has_8 = any(str(s.get("section", "")) == "117.8" or re.search(r"117[._-]8\b", str(s.get("file", "")))
                    for s in m.get("sections", []))
        if has_8:
            return child, m
    return None, None


def collect_cfr(root: Path, files: dict, out: Path) -> dict:
    folder, manifest = find_cfr_split(root)
    if folder is None:
        return {"available": False, "reason": CFR_UNAVAILABLE_REASON,
                "library_has": "unsplit whole-Part text file only"}
    rel_dir = CFR_RELEASE_DIR
    (out / rel_dir).mkdir(parents=True, exist_ok=True)
    manifest_bytes = (folder / "manifest.json").read_bytes()
    (out / rel_dir / "manifest.json").write_bytes(manifest_bytes)
    lib_rel = f"{CFR_DIR}/{folder.name}"
    files[f"{rel_dir}/manifest.json"] = {"sha256": sha256_bytes(manifest_bytes),
                                         "source": f"library:{lib_rel}/manifest.json",
                                         "verified": True, "verified_by": "custodian-release"}
    sections = []
    for sec in manifest.get("sections", []):
        name = sec.get("file")
        if not name or "/" in name or "\\" in name:
            raise Refused("cfr-117: manifest names an unsafe section file")
        src = folder / name
        if not src.is_file():
            raise Refused(f"cfr-117: {name} listed in the manifest but not on disk")
        raw = src.read_bytes()
        expected = sec.get("body_sha256")
        if not expected:
            raise Refused(f"cfr-117: {name} carries no body_sha256 in the library manifest, so it cannot be verified")
        if sha256_bytes(section_body(raw.decode("utf-8-sig")).encode("utf-8")) != expected:
            raise Refused(f"cfr-117: {name} does not match the body hash the library manifest records")
        (out / rel_dir / name).write_bytes(raw)
        files[f"{rel_dir}/{name}"] = {"sha256": sha256_bytes(raw), "source": f"library:{lib_rel}/{name}",
                                      "body_sha256": expected, "verified": True,
                                      "verified_by": "custodian-release"}
        sections.append({"file": name, "section": sec.get("section"), "title": sec.get("title")})
    return {"available": True, "manifest": f"{rel_dir}/manifest.json", "sections": sections}


# ---------------------------------------------------------------------------
# Maintainer-authored files
# ---------------------------------------------------------------------------
def load_corpus_file(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if path.suffix == ".md":
        if not text.startswith("---"):
            raise Refused(f"{path.relative_to(ROOT)}: markdown corpus file has no frontmatter")
        _, fm, body = text.split("---", 2)
        data = yaml.safe_load(fm) or {}
        if not isinstance(data, dict):
            raise Refused(f"{path.relative_to(ROOT)}: frontmatter is not a mapping")
        data = {**data, "body_markdown": body.lstrip("\n")}
    else:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise Refused(f"{path.relative_to(ROOT)}: not a YAML mapping")
    return data, raw


def verification_of(data: dict) -> tuple[bool, str | None]:
    """Report the flag as the file carries it. Never set it.

    `verified` is true only when maintainer_verified is true AND the
    provenance validate_corpus.py demands is present. The flag itself is
    never touched; a true flag without provenance is reported as unverified
    here and is an error in validate_corpus.py, which the build runs first.
    """
    if data.get("maintainer_verified") is True and all(data.get(k) for k in PROVENANCE_KEYS):
        return True, "maintainer"
    return False, None


def collect_maintainer(files: dict, out: Path) -> dict:
    served = []
    for rel in MAINTAINER_FILES:
        src = CORPUS / rel
        if not src.is_file():
            raise Refused(f"corpus/{rel} is missing from this checkout")
        data, raw = load_corpus_file(src)
        verified, by = verification_of(data)
        target_rel = "corpus/" + re.sub(r"\.(yaml|yml|md)$", ".json", rel)
        payload = dump_json(data)
        target = out / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        files[target_rel] = {
            "sha256": sha256_bytes(payload),
            "source": f"repo:corpus/{rel}",
            "source_sha256_yaml": sha256_bytes(raw),
            "maintainer_verified": data.get("maintainer_verified") is True,
            "verified": verified, "verified_by": by,
        }
        served.append(target_rel)
    return {"files": served,
            "verified": sum(1 for f in served if files[f]["verified"]),
            "unverified": sum(1 for f in served if not files[f]["verified"])}


def collect_agents(files: dict, out: Path) -> list[str]:
    served = []
    for src in sorted(AGENTS.rglob("*.md")):
        rel = src.relative_to(ROOT).as_posix()
        raw = src.read_bytes()
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        files[rel] = {"sha256": sha256_bytes(raw), "source": f"repo:{rel}",
                      "verified": None, "verified_by": None, "kind": "agent-prompt"}
        served.append(rel)
    if "agents/conductor.md" not in served:
        raise Refused("agents/conductor.md is missing from this checkout")
    return served


def collect_disclaimer(files: dict, out: Path) -> str:
    src = ROOT / "DISCLAIMER.md"
    if not src.is_file():
        raise Refused("DISCLAIMER.md is missing from this checkout")
    raw = src.read_bytes()
    (out / "DISCLAIMER.md").write_bytes(raw)
    files["DISCLAIMER.md"] = {"sha256": sha256_bytes(raw), "source": "repo:DISCLAIMER.md",
                              "verified": None, "verified_by": None, "kind": "disclaimer"}
    return "DISCLAIMER.md"


def collect_exclusions(root: Path, release_id: str, files: dict, out: Path) -> dict:
    path, _ = lp.find_ci(root, "ROBOT_READABLE_DIRECTORY/MANIFESTS/DOHA_CURRENT_PATHS.jsonl")
    if not path or not path.is_file():
        raise Refused("DOHA_CURRENT_PATHS.jsonl is missing from the library release")
    excluded = []
    total = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            if rec.get("answer_eligible") is False and rec.get("document_id"):
                excluded.append(rec["document_id"])
    excluded.sort()
    payload = dump_json({
        "library_release": release_id,
        "derived_from": "ROBOT_READABLE_DIRECTORY/MANIFESTS/DOHA_CURRENT_PATHS.jsonl",
        "rule": "document_id of every row with answer_eligible: false",
        "manifest_rows": total,
        "count": len(excluded),
        "document_ids": excluded,
    })
    (out / "doha-exclusions.json").write_bytes(payload)
    files["doha-exclusions.json"] = {"sha256": sha256_bytes(payload), "source": "derived:DOHA_CURRENT_PATHS.jsonl",
                                     "verified": True, "verified_by": "custodian-release", "kind": "derived"}
    return {"file": "doha-exclusions.json", "count": len(excluded), "manifest_rows": total}


# ---------------------------------------------------------------------------
# wrangler.jsonc
# ---------------------------------------------------------------------------
def strip_jsonc(text: str) -> str:
    out, i, n = [], 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True; out.append(c); i += 1; continue
        if text.startswith("//", i):
            j = text.find("\n", i); i = n if j < 0 else j; continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2); i = n if j < 0 else j + 2; continue
        out.append(c); i += 1
    cleaned = "".join(out)
    return re.sub(r",(\s*[}\]])", r"\1", cleaned)


def read_config(path: Path) -> tuple[str, dict]:
    text = path.read_text(encoding="utf-8")
    return text, json.loads(strip_jsonc(text))


def set_shard(text: str, binding: str, name: str, database_id: str) -> str:
    pat = re.compile(r'(\{\s*"binding"\s*:\s*"%s"\s*,\s*"database_name"\s*:\s*)"[^"]*"(\s*,\s*"database_id"\s*:\s*)"[^"]*"'
                     % re.escape(binding))
    if not pat.search(text):
        raise Refused(f"wrangler.jsonc has no D1 binding {binding} in the expected one-line shape")
    return pat.sub(lambda m: f'{m.group(1)}"{name}"{m.group(2)}"{database_id}"', text, count=1)


def parse_shards(spec: str | None, current: list[dict]) -> list[dict]:
    """--doha-shards s1,s2,s3 or name=id,name=id,name=id. Three entries, in
    binding order S1,S2,S3. A bare name needs its database id resolved from
    `wrangler d1 list`, which only works with a Cloudflare login."""
    if not spec:
        return current
    items = [s.strip() for s in spec.split(",") if s.strip()]
    if len(items) != 3:
        raise Refused("--doha-shards needs exactly three databases: s1,s2,s3")
    shards = []
    for binding, item in zip(("S1", "S2", "S3"), items):
        name, _, dbid = item.partition("=")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            raise Refused("--doha-shards holds a database name that is not a plain identifier")
        shards.append({"binding": binding, "database_name": name, "database_id": dbid or None})
    if any(not s["database_id"] for s in shards):
        listing = wrangler_d1_list()
        for s in shards:
            if not s["database_id"]:
                match = next((d for d in listing if d.get("name") == s["database_name"]), None)
                if not match or not match.get("uuid"):
                    raise Refused(f"cannot resolve a database id for {s['database_name']}; pass name=id")
                s["database_id"] = match["uuid"]
    return shards


def wrangler_d1_list() -> list[dict]:
    try:
        r = subprocess.run(["npx", "wrangler", "d1", "list", "--json"], cwd=ROOT,
                           capture_output=True, text=True, shell=(os.name == "nt"), timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Refused(f"wrangler d1 list failed: {exc}") from exc
    if r.returncode != 0:
        raise Refused("wrangler d1 list failed (is wrangler installed and logged in?)")
    try:
        return json.loads(r.stdout[r.stdout.index("["):])
    except (ValueError, json.JSONDecodeError) as exc:
        raise Refused("wrangler d1 list returned no JSON") from exc


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def run_checks() -> dict:
    results = {}
    for label, args in (("validate_corpus", [sys.executable, str(ROOT / "scripts" / "validate_corpus.py")]),
                        ("run_tests", [sys.executable, str(ROOT / "tests" / "run_tests.py")])):
        print(f"  running {label} …", flush=True)
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            tail = (r.stdout + r.stderr).strip().splitlines()[-12:]
            raise Refused(f"{label} failed on this checkout:\n    " + "\n    ".join(tail))
        results[label] = "passed"
    return results


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build(root: Path, out: Path, shards: list[dict], checks: dict) -> dict:
    release = rc.approved_release(root)  # raises ValueError when not approved
    release_id = release["release_id"]
    approval = release["approval"]

    files: dict[str, dict] = {}
    directives = {key: collect_directive(root, key, files, out) for key in DIRECTIVES}
    cfr = collect_cfr(root, files, out)
    maintainer = collect_maintainer(files, out)
    agents = collect_agents(files, out)
    disclaimer = collect_disclaimer(files, out)
    exclusions = collect_exclusions(root, release_id, files, out)
    version_line = (CORPUS / "VERSION").read_text(encoding="utf-8").strip()
    corpus_version = version_line.split()[0] if version_line else "unknown"
    commit, dirty = repo_commit()

    manifest = {
        "schema_version": "1.0",
        "server": WORKER_NAME,
        "corpus_version": corpus_version,
        "corpus_version_line": version_line,
        "repo_commit": commit,
        "repo_dirty": dirty,
        "library_release": release_id,
        "library_approval": {"approved_by": approval.get("approved_by"),
                             "approved_utc": approval.get("approved_utc"),
                             "note": approval.get("note")},
        "library_published_utc": release["state"].get("published_utc"),
        "doha_shards": [s["database_name"] for s in shards],
        "built_utc": utc_now(),
        "checks": checks,
        "directives": directives,
        "cfr_117": cfr,
        "maintainer": maintainer,
        "agents": agents,
        "disclaimer": disclaimer,
        "doha_exclusions": exclusions,
        "unverified_sentence": UNVERIFIED_SENTENCE,
        "counts": {"files": len(files) + 1,
                   "government_files": sum(1 for f in files.values() if f["source"].startswith("library:")),
                   "maintainer_files": len(maintainer["files"]),
                   "maintainer_verified": maintainer["verified"],
                   "maintainer_unverified": maintainer["unverified"]},
        "files": files,
    }
    (out / "manifest.json").write_bytes(dump_json(manifest))
    return manifest


def manifest_fingerprint(m: dict) -> str:
    """Everything in a manifest except when it was built, for the
    nothing-changed decision."""
    copy = {k: v for k, v in m.items() if k != "built_utc"}
    return sha256_bytes(dump_json(copy))


def replace_dir(src: Path, dest: Path) -> None:
    if dest.exists():
        if not (dest / "manifest.json").exists() and any(dest.iterdir()):
            raise Refused(f"{dest} exists and is not a previous release build; refusing to overwrite it")
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)


def rpc_live_get_release(url: str) -> dict:
    """POST initialize + tools/call get_release to the deployed Worker. The only
    network call in this repo's scripts, made solely after --deploy to confirm
    the deployment serves the release that was just built."""
    import urllib.request
    body = json.dumps([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "hosted_release.py", "version": "1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_release", "arguments": {}}},
    ]).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"content-type": "application/json", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - our own Worker
        payload = json.loads(resp.read().decode("utf-8"))
    for msg in payload if isinstance(payload, list) else [payload]:
        if msg.get("id") == 2:
            return msg.get("result", {}).get("structuredContent", {})
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--library", help="DCSA Library root (default: the remembered location)")
    ap.add_argument("--doha-shards", help="three D1 database names s1,s2,s3 (or name=id,…) to bind")
    ap.add_argument("--deploy", action="store_true", help="run wrangler deploy, then confirm the live get_release")
    ap.add_argument("--dry-run", action="store_true", help="build into a temporary folder; write nothing under mcp/")
    ap.add_argument("--out", help=f"release folder (default {DEFAULT_OUT.relative_to(ROOT)})")
    ap.add_argument("--config", help="wrangler.jsonc to read and rewrite (default mcp/wrangler.jsonc)")
    ap.add_argument("--skip-checks", action="store_true",
                    help="skip validate_corpus.py and tests/run_tests.py (the test suite only; refused with --deploy)")
    args = ap.parse_args()

    try:
        if args.deploy and (args.dry_run or args.skip_checks):
            raise Refused("--deploy cannot be combined with --dry-run or --skip-checks")
        root, how = lp.resolve(args.library)
        if root is None or not lp.is_library_root(lp.clean_user_path(str(root))):
            raise Refused("DCSA Library not found. Pass --library \"<root containing START_HERE_FOR_ROBOTS.json>\". "
                          "This script never downloads it.")
        root = lp.clean_user_path(str(root)).resolve()
        print(f"library: {root}  ({how})")

        config_path = Path(args.config) if args.config else DEFAULT_CONFIG
        config_text, config = read_config(config_path)
        current_shards = config.get("d1_databases", [])
        shards = parse_shards(args.doha_shards, current_shards)
        if not args.doha_shards:
            print("D1 shards: keeping the current bindings; decision text may be older than the reference text.")

        checks = {"validate_corpus": "skipped", "run_tests": "skipped"} if args.skip_checks else run_checks()

        with tempfile.TemporaryDirectory(prefix="hosted-release-") as td:
            staging = Path(td) / "release"
            staging.mkdir()
            manifest = build(root, staging, shards, checks)

            out = Path(args.out) if args.out else DEFAULT_OUT
            previous = None
            if (out / "manifest.json").is_file():
                try:
                    previous = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    previous = None
            unchanged = previous is not None and manifest_fingerprint(previous) == manifest_fingerprint(manifest)

            # The release ids travel in manifest.json, which the Worker reads;
            # they are also passed as deploy-time vars (--var) so get_release can
            # report a deployment whose vars and manifest disagree. wrangler.jsonc
            # itself is rewritten only for a deliberate shard rebinding, which is
            # a change to commit.
            deploy_vars = {"RELEASE_ID": manifest["library_release"],
                           "CORPUS_VERSION": manifest["corpus_version"],
                           "REPO_COMMIT": manifest["repo_commit"]}
            new_text = config_text
            if args.doha_shards:
                for s in shards:
                    new_text = set_shard(new_text, s["binding"], s["database_name"], s["database_id"])
            config_changed = new_text != config_text

            print(f"\nrelease:  library {manifest['library_release']} (approved by "
                  f"{manifest['library_approval']['approved_by']} {manifest['library_approval']['approved_utc']})")
            print(f"          corpus {manifest['corpus_version']}  commit {manifest['repo_commit']}"
                  + ("  (DIRTY CHECKOUT)" if manifest["repo_dirty"] else ""))
            c = manifest["counts"]
            print(f"files:    {c['files']} total — {c['government_files']} Government (verified by the "
                  f"Custodian release), {c['maintainer_files']} maintainer-authored "
                  f"({c['maintainer_verified']} verified, {c['maintainer_unverified']} unverified), "
                  f"{len(manifest['agents'])} agent prompts")
            print(f"32 CFR §117.8: {'available' if manifest['cfr_117']['available'] else 'UNAVAILABLE — ' + manifest['cfr_117']['reason']}")
            print(f"exclusions: {manifest['doha_exclusions']['count']} ineligible document ids of "
                  f"{manifest['doha_exclusions']['manifest_rows']} manifest rows")
            print("deploy vars: " + "  ".join(f"{k}={v}" for k, v in deploy_vars.items()))
            print("D1:       " + ", ".join(s["database_name"] for s in shards))
            print(f"release folder {'unchanged' if unchanged else 'changed'}; wrangler.jsonc "
                  f"{'changed' if config_changed else 'unchanged'}")

            if args.dry_run:
                print(f"\nDRY RUN — nothing written under mcp/. Built {c['files']} files in a temporary folder.")
                return EXIT_OK

            replace_dir(staging, out)
            if config_changed:
                config_path.write_text(new_text, encoding="utf-8")
            print(f"\nwrote {out}" + (f" and {config_path}" if config_changed else ""))

        if not args.deploy:
            if unchanged and not config_changed:
                print("nothing changed since the previous build.")
            print("not deployed (no --deploy). Deploy with: npx wrangler deploy --config mcp/wrangler.jsonc "
                  + " ".join(f"--var {k}:{v}" for k, v in deploy_vars.items()))
            return EXIT_OK

        print("\ndeploying …", flush=True)
        r = subprocess.run(["npx", "wrangler", "deploy", "--config", str(config_path),
                            *[f"--var={k}:{v}" for k, v in deploy_vars.items()]],
                           cwd=ROOT, shell=(os.name == "nt"))
        if r.returncode != 0:
            raise Refused("wrangler deploy failed")
        route = (config.get("routes") or [{}])[0].get("pattern", "")
        url = "https://" + route.rstrip("*")
        print(f"confirming the live release at {url} …")
        live = rpc_live_get_release(url)
        want = {"library_release": manifest["library_release"], "corpus_version": manifest["corpus_version"],
                "repo_commit": manifest["repo_commit"]}
        got = {k: (live.get("release") or {}).get(k) for k in want}
        if got != want:
            print(f"LIVE MISMATCH: deployed {want}, live reports {got}")
            return EXIT_LIVE_MISMATCH
        print("live get_release reports the new ids. Done.")
        return EXIT_OK
    except Refused as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED
    except ValueError as exc:
        print(f"REFUSED: the library release is not approved for use as a source: {exc}")
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
