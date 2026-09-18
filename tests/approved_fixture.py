"""Add synthetic published metadata to a TEMPORARY copy of the mini-library.

No production gate is mocked or bypassed. Old partial-bundle fixtures alone are
intentionally no longer sufficient proof of approved evidence access.
"""
import contextlib
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release_contract as rc


def prepare(root):
    def write(relative, data):
        p = root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")
    release = "synthetic-test-release"
    index_path = f"LOCAL_INDEXES/CUSTODIAN/{release}/rule.sqlite"
    index = {"production_path": index_path, "default_allowed": True,
             "allowed_intents": ["contractor_or_fso_obligation"], "chunks": 1}
    paths = [index_path, "LOCAL_INDEXES/DOHA_CASE_TOPICS_FTS.sqlite", "LOCAL_INDEXES/DOHA_CURRENT_PATHS.sqlite"]
    for relative in paths:
        p = root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(sqlite3.connect(p)) as db:
            db.execute("CREATE TABLE corpus (document_id,answer_eligibility,authority_role)")
            db.execute("INSERT INTO corpus VALUES ('synthetic','answer_eligible','controlling_regulation')")
            db.commit()
    approval = {"release_id": release, "approved_by": "synthetic-fixture", "approved_utc": "2000-01-01T00:00:00Z"}
    expected = {"current_release": rc.POINTER, "library_state": rc.STATE, "index_catalog": rc.CATALOG,
                "query_policy": rc.QUERY, "access_policy": rc.POLICY, "retrieval": rc.CONFIG, "doha_router": rc.ROUTER}
    entry = json.loads((root / "START_HERE_FOR_ROBOTS.json").read_text())
    entry.update(expected, doha_local_indexes=paths[1:])
    write("START_HERE_FOR_ROBOTS.json", entry)
    write("ROBOT_READABLE_DIRECTORY/START_HERE.json", expected)
    write(rc.STATE, dict(release_id=release, release_status="published", production_response_ready=True,
                        production_integrity_healthy=True, publication_blockers=[], approved_indexes=[index],
                        approval=approval, published_utc="2000-01-01T00:00:00Z"))
    write(rc.CATALOG, dict(release_id=release,indexes=[index],default_sequence=[index_path]))
    write(rc.QUERY, dict(release_id=release,indexes=[index],fail_closed=True,content_source="robot_only"))
    write(rc.POLICY, {"content_access": dict(approved_indexes_mode="resolve_from_index_catalog", doha_approved_indexes=paths[1:])})
    write(rc.CONFIG, dict(default_index_mode="resolve_from_index_catalog", index_catalog=rc.CATALOG, query_policy=rc.QUERY,
                          current_release_pointer=rc.POINTER, access_policy=rc.POLICY, library_state=rc.STATE,
                          entry_point="START_HERE_FOR_ROBOTS.json", doha_index=paths[1], doha_current_paths_index=paths[2]))
    router = json.loads((root / rc.ROUTER).read_text())
    router.update(doha_content_index=paths[1],current_doha_path_index=paths[2])
    write(rc.ROUTER, router)
    (root / "AGENTS.md").write_text("Synthetic test library. Robot-only approved retrieval.")
    write(rc.POINTER, dict(release_id=release, approval=approval, published_utc="2000-01-01T00:00:00Z",
                           metadata_sha256={p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in (rc.STATE,rc.CATALOG,rc.QUERY,rc.POLICY,rc.CONFIG)}))
